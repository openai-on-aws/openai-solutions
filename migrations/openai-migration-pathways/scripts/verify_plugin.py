#!/usr/bin/env python3
"""Offline publication checks for manifests, evidence, examples and local documentation."""
import argparse
import ast
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlparse
import evaluate_routes
import package_plugin
import verify_report


def verify(root, repository=None):
    root = Path(root).resolve()
    manifest = package_plugin.validate_source(root)
    files = package_plugin.inventory(root)
    for name in ("LICENSE", "LICENSE-DOCS.md", "LICENSING.md", "THIRD-PARTY-NOTICES.md"):
        if not (root / name).is_file():
            raise ValueError("Missing publication notice: " + name)
    python_files = 0
    json_files = 0
    links = 0
    for relative in files:
        path = root / relative
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=str(relative))
            python_files += 1
        elif path.suffix == ".json":
            verify_report.load(path)
            json_files += 1
        elif path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                target = target.strip("<>")
                if urlparse(target).scheme or target.startswith("#") or "<" in target or ">" in target:
                    continue
                name = unquote(target.split("#")[0])
                if not name:
                    continue
                destination = (path.parent / name).resolve()
                if not destination.is_relative_to(root) or not destination.exists():
                    raise ValueError("Missing/escaped local documentation link: " + str(relative) + " -> " + name)
                links += 1
    registry = verify_report.load(root / "data/capabilities.json")
    evaluate_routes.validate_registry(registry, root / "data")
    verify_report.audit(root / "examples/discovery-report", historical=True)
    if repository is not None:
        repository = Path(repository).resolve()
        catalog = verify_report.load(repository / ".agents/plugins/marketplace.json")
        if catalog["name"] != "openai-solutions":
            raise ValueError("Unexpected repository marketplace identity")
        entries = [p for p in catalog["plugins"] if p["name"] == manifest["name"]]
        if len(entries) != 1:
            raise ValueError("Marketplace must contain the plugin exactly once")
        entry = entries[0]
        if entry["source"]["source"] != "local" or not entry["source"]["path"].startswith("./"):
            raise ValueError("Repository plugin must use a relative local source")
        if (repository / entry["source"]["path"]).resolve() != root:
            raise ValueError("Marketplace points at a different plugin")
        if entry["policy"] != {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}:
            raise ValueError("Unexpected plugin installation policy")
    return {"version": manifest["version"], "plugin_files": len(files), "python_files": python_files,
            "json_files": json_files, "local_documentation_links": links,
            "evidence_snapshots": len(registry["sources"]), "repository_marketplace_checked": repository is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path)
    args = parser.parse_args()
    result = verify(Path(__file__).resolve().parents[1], args.repository_root)
    print(json.dumps(result, indent=2))
    print("PASS: offline publication checks; no live account, model or deployment verification.")
