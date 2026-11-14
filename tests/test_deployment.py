"""Local tests for the deployment exchange and backup-retention safeguards."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("retention", REPO / "scripts/deploy-retention.py")
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.root = self.parent / "public_html"
        self.root.mkdir()
        self.release = self.parent / ".navikarana-release-2-1"
        self.release.mkdir()
        self.version(self.root, "2-1")

    def version(self, directory, run):
        (directory / "deployment-version.json").write_text(
            json.dumps({"site": retention.SITE, "run": run}), encoding="utf-8"
        )

    def managed_backup(self):
        self.version(self.release, "1-1")
        (self.release / "index.html").write_text("old site", encoding="utf-8")
        nested = self.release / "assets"
        nested.mkdir()
        (nested / "style.css").write_text("old css", encoding="utf-8")
        entries = []
        for path in sorted(self.release.rglob("*")):
            if path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                entries.append(f"{digest}  ./{path.relative_to(self.release).as_posix()}\n")
        (self.release / ".deployment-manifest").write_text("".join(entries), encoding="utf-8")

    def mark_and_expire(self):
        retention.mark(self.root, self.release, "2-1")
        marker = self.release / retention.MARKER
        data = json.loads(marker.read_text(encoding="utf-8"))
        data["retired_at"] = time.time() - retention.GRACE_SECONDS - 1
        marker.write_text(json.dumps(data), encoding="utf-8")

    def test_isolated_preflight_does_not_change_live_site(self):
        (self.root / "index.html").write_text("live", encoding="utf-8")
        subprocess.run([sys.executable, REPO / "scripts/check-exchange.py", self.root], check=True)
        self.assertEqual((self.root / "index.html").read_text(encoding="utf-8"), "live")
        self.assertEqual({p.name for p in self.parent.iterdir()}, {"public_html", self.release.name})

    def test_exchange_keeps_previous_site(self):
        (self.root / "index.html").write_text("old", encoding="utf-8")
        for name in ("index.html", "404.html", ".htaccess", "deployment-version.json", ".deployment-manifest"):
            (self.release / name).write_text("new", encoding="utf-8")
        subprocess.run([sys.executable, REPO / "scripts/deploy-exchange.py", self.root, self.release], check=True)
        self.assertEqual((self.root / "index.html").read_text(encoding="utf-8"), "new")
        self.assertEqual((self.release / "index.html").read_text(encoding="utf-8"), "old")

    def test_exchange_rejects_unrecognized_stage(self):
        other = self.parent / "other"
        other.mkdir()
        result = subprocess.run(
            [sys.executable, REPO / "scripts/deploy-exchange.py", self.root, other],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.root.is_dir())
        self.assertTrue(other.is_dir())

    def test_backup_is_retained_until_grace_period(self):
        self.managed_backup()
        retention.mark(self.root, self.release, "2-1")
        retention.clean(self.root)
        self.assertTrue(self.release.exists())

    def test_expired_unchanged_managed_backup_is_removed(self):
        self.managed_backup()
        self.mark_and_expire()
        retention.clean(self.root)
        self.assertFalse(self.release.exists())
        self.assertTrue(self.root.exists())

    def test_changed_missing_extra_and_symlinked_files_are_retained(self):
        self.managed_backup()
        self.mark_and_expire()
        target = self.release / "index.html"
        original = target.read_bytes()
        target.write_text("changed", encoding="utf-8")
        retention.clean(self.root)
        self.assertTrue(self.release.exists())
        target.unlink()
        retention.clean(self.root)
        self.assertTrue(self.release.exists())
        target.write_bytes(original)
        extra = self.release / "extra.txt"
        extra.write_text("extra", encoding="utf-8")
        retention.clean(self.root)
        self.assertTrue(self.release.exists())
        extra.unlink()
        os.symlink("index.html", self.release / "link")
        retention.clean(self.root)
        self.assertTrue(self.release.exists())

    def test_unknown_and_git_backups_are_never_marked(self):
        retention.mark(self.root, self.release, "2-1")
        self.assertFalse((self.release / retention.MARKER).exists())
        self.managed_backup()
        (self.release / ".git").mkdir()
        retention.mark(self.root, self.release, "2-1")
        self.assertFalse((self.release / retention.MARKER).exists())

    def test_wrong_live_version_is_not_marked(self):
        self.managed_backup()
        with self.assertRaises(ValueError):
            retention.mark(self.root, self.release, "3-1")
        self.assertFalse((self.release / retention.MARKER).exists())

    def test_unmarked_or_unrecognized_directory_is_not_deleted(self):
        self.managed_backup()
        retention.clean(self.root)
        self.assertTrue(self.release.exists())
        self.mark_and_expire()
        other = self.parent / "unknown"
        self.release.rename(other)
        retention.clean(self.root)
        self.assertTrue(other.exists())

    def test_backup_cannot_be_cleaned_for_a_different_web_root(self):
        self.managed_backup()
        self.mark_and_expire()
        other_root = self.parent / "different-root"
        other_root.mkdir()
        retention.clean(other_root)
        self.assertTrue(self.release.exists())


if __name__ == "__main__":
    unittest.main()
