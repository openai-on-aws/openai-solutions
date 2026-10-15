#!/usr/bin/env python3
"""Package this plugin as a local marketplace folder and ZIP. Does not install/publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def inventory(source):
    files = []
    for directory, dirs, names in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in dirs + sorted(names):
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError("Symlink cannot be packaged: " + str(path.relative_to(source)))
            if name == ".env" or (name.startswith(".env.") and name != ".env.example") or name in {
                    "credentials", "credentials.json", "id_rsa", "id_ed25519"}:
                raise ValueError("Review credential-like file before packaging: " + str(path.relative_to(source)))
        for name in sorted(names):
            if name not in SKIP_FILES and not name.endswith((".pyc", ".pyo")):
                path = Path(directory) / name
                relative = path.relative_to(source)
                if any(c in str(relative) for c in "\n\r\\"):
                    raise ValueError("Unsupported archive path: " + str(relative))
                files.append(relative)
    return sorted(files)


def validate_source(source):
    manifest = json.loads((source / "plugin.json").read_text())
    fallback = json.loads((source / ".codex-plugin/plugin.json").read_text())
    for field in ("name", "version", "description", "author", "repository", "homepage", "license"):
        if manifest.get(field) != fallback.get(field):
            raise ValueError("Manifest mismatch: " + field)
    if manifest["extensions"]["com.openai"]["interface"] != fallback["interface"]:
        raise ValueError("Manifest interface mismatch")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", manifest["name"]):
        raise ValueError("Unsafe plugin name")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[+.-][a-zA-Z0-9.-]+)?", manifest["version"]):
        raise ValueError("Invalid release version")
    paths = ["README.md", "INSTALL.md", "skills/" + manifest["name"] + "/SKILL.md"]
    paths += [fallback["interface"][k] for k in ("composerIcon", "logo", "logoDark")
              if k in fallback["interface"]]
    for name in paths:
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError("Missing/escaped manifest artifact: " + name)
    return manifest


def package(source, destination, marketplace_name=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    archive = destination.with_name(destination.name + ".zip")
    archive_checksum = archive.with_name(archive.name + ".sha256")
    if destination.is_relative_to(source):
        raise ValueError("Release output must be outside the plugin source")
    if destination.exists() or archive.exists() or archive_checksum.exists():
        raise ValueError("Release folder/archive already exists; choose a new destination")
    manifest = validate_source(source)
    files = inventory(source)
    name = manifest["name"]
    marketplace_name = marketplace_name or name
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", marketplace_name):
        raise ValueError("Invalid marketplace name")
    destination.mkdir(parents=True)
    plugin = destination / "plugins" / name
    for relative in files:
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)
    marketplace = {
        "name": marketplace_name,
        "interface": {"displayName": manifest["extensions"]["com.openai"]["interface"]["displayName"]},
        "plugins": [{"name": name, "source": {"source": "local", "path": "./plugins/" + name},
                     "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                     "category": "Developer Tools"}],
    }
    catalog = destination / ".agents/plugins/marketplace.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps(marketplace, indent=2) + "\n")
    (destination / "README.md").write_text(
        "# OpenAI Migration Pathways " + manifest["version"] + "\n\n"
        "This folder is a local plugin marketplace. Keep its hidden `.agents` directory.\n\n"
        "Follow [installation instructions](plugins/" + name + "/INSTALL.md), "
        "read the [plugin overview](plugins/" + name + "/README.md), or inspect the "
        "[sample report](plugins/" + name + "/examples/discovery-report/assessment.md).\n\n"
        "Register this extracted folder with `codex plugin marketplace add /absolute/path/to/this-folder`, "
        "then install `" + name + "@" + marketplace_name + "` from the app or CLI. Start a new chat after installation.\n\n"
        "CHECKSUMS.sha256 covers every packaged file except itself. The ZIP contains the same folder. "
        "No GitHub or workspace publication is performed by packaging.\n")
    packaged_files = inventory(destination)
    checksum = "".join(hashlib.sha256((destination / p).read_bytes()).hexdigest() + "  " + p.as_posix() + "\n"
                       for p in packaged_files)
    (destination / "CHECKSUMS.sha256").write_text(checksum)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for relative in inventory(destination):
            bundle.write(destination / relative, destination.name + "/" + relative.as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("Archive integrity verification failed")
        for relative in inventory(destination):
            if bundle.read(destination.name + "/" + relative.as_posix()) != (destination / relative).read_bytes():
                raise ValueError("Archive/folder mismatch: " + str(relative))
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    with archive_checksum.open("x") as output:
        output.write(archive_hash + "  " + archive.name + "\n")
    return {"version": manifest["version"], "marketplace_name": marketplace_name,
            "plugin_files": len(files), "folder": str(destination), "archive": str(archive),
            "archive_sha256": archive_hash, "archive_checksum_file": str(archive_checksum)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New marketplace folder, outside the plugin")
    parser.add_argument("--marketplace-name", help="Marketplace identity; defaults to the plugin name")
    args = parser.parse_args()
    try:
        result = package(Path(__file__).resolve().parents[1], args.destination, args.marketplace_name)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, "Packaging failed: " + str(exc) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
