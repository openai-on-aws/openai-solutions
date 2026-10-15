import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import package_plugin


class PackageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        manifest = {"name": "sample-plugin", "version": "0.4.1", "description": "Fixture",
                    "author": {"name": "Fixture"}, "interface": {"displayName": "Sample"}}
        (self.source / ".codex-plugin").mkdir(parents=True)
        (self.source / ".codex-plugin/plugin.json").write_text(json.dumps(manifest))
        portable = {k: v for k, v in manifest.items() if k != "interface"}
        portable["extensions"] = {"com.openai": {"interface": manifest["interface"]}}
        (self.source / "plugin.json").write_text(json.dumps(portable))
        skill = self.source / "skills/sample-plugin"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("Fixture")
        for name in ["README.md", "INSTALL.md", ".DS_Store"]:
            (self.source / name).write_text("Fixture")
        cache = self.source / "__pycache__"
        cache.mkdir()
        (cache / "private.pyc").write_bytes(b"not for release")
        self.destination = self.root / "release"

    def test_archive_matches_checksums_and_preserves_hidden_marketplace(self):
        result = package_plugin.package(self.source, self.destination)
        sums = (self.destination / "CHECKSUMS.sha256").read_text().splitlines()
        with zipfile.ZipFile(result["archive"]) as bundle:
            self.assertIn("release/.agents/plugins/marketplace.json", bundle.namelist())
            self.assertFalse(any(".DS_Store" in p or "__pycache__" in p for p in bundle.namelist()))
            for line in sums:
                digest, path = line.split("  ", 1)
                self.assertEqual(digest, hashlib.sha256(bundle.read("release/" + path)).hexdigest())

    def test_manifest_divergence(self):
        path = self.source / "plugin.json"
        data = json.loads(path.read_text())
        data["version"] = "1.0.0"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Manifest mismatch"):
            package_plugin.package(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_reject_symlink(self):
        (self.source / "linked").symlink_to(self.source / "README.md")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            package_plugin.package(self.source, self.destination)

    def test_reject_credential_file(self):
        (self.source / ".env").write_text("TOKEN=fixture")
        with self.assertRaisesRegex(ValueError, "credential-like"):
            package_plugin.package(self.source, self.destination)

    def test_do_not_overwrite_existing_release(self):
        self.destination.mkdir()
        (self.destination / "keep").write_text("Keep")
        with self.assertRaisesRegex(ValueError, "already exists"):
            package_plugin.package(self.source, self.destination)
        self.assertEqual((self.destination / "keep").read_text(), "Keep")

    def test_repository_marketplace_and_archive_checksum(self):
        result = package_plugin.package(self.source, self.destination, "openai-solutions")
        catalog = json.loads((self.destination / ".agents/plugins/marketplace.json").read_text())
        self.assertEqual(catalog["name"], "openai-solutions")
        self.assertIn("sample-plugin@openai-solutions", (self.destination / "README.md").read_text())
        digest, filename = Path(result["archive_checksum_file"]).read_text().strip().split("  ", 1)
        self.assertEqual(filename, Path(result["archive"]).name)
        self.assertEqual(digest, hashlib.sha256(Path(result["archive"]).read_bytes()).hexdigest())

    def test_do_not_overwrite_existing_archive_checksum(self):
        path = self.root / "release.zip.sha256"
        path.write_text("Existing release")
        with self.assertRaisesRegex(ValueError, "already exists"):
            package_plugin.package(self.source, self.destination)
        self.assertEqual(path.read_text(), "Existing release")

    def test_invalid_marketplace_name_has_no_output(self):
        with self.assertRaisesRegex(ValueError, "Invalid marketplace"):
            package_plugin.package(self.source, self.destination, "../elsewhere")
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
