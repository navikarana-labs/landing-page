#!/usr/bin/env python3
"""Retain verified backups for at least an hour and conservatively clean them."""

import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path


RELEASE = re.compile(r"\.navikarana-release-[0-9]+-[0-9]+\Z")
RUN = re.compile(r"[0-9]+-[0-9]+\Z")
SITE = "navikarana-landing-page"
MARKER = ".navikarana-retired.json"
GRACE_SECONDS = 3600


def load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def web_root(path):
    root = Path(os.path.abspath(path))
    if root == root.parent or root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid live document root")
    return root


def valid_release(root, release):
    return (release.parent == root.parent and release != root and RELEASE.fullmatch(release.name)
            and not release.is_symlink() and release.is_dir())


def mark(root, release, expected_run):
    if not valid_release(root, release) or not RUN.fullmatch(expected_run):
        raise ValueError("Invalid backup path or run ID")
    live = load_json(root / "deployment-version.json")
    if live.get("site") != SITE or live.get("run") != expected_run:
        raise ValueError("Live build does not match the verified deployment")
    # Never automatically delete the original Git checkout or unknown builds.
    manifest = release / ".deployment-manifest"
    version = release / "deployment-version.json"
    if (os.path.lexists(release / ".git") or manifest.is_symlink() or not manifest.is_file()
            or version.is_symlink() or not version.is_file()):
        print("Previous site is not a managed build; retaining it without automatic cleanup.")
        return
    try:
        previous = load_json(version)
        if previous.get("site") != SITE or not RUN.fullmatch(str(previous.get("run", ""))):
            print("Previous site has no managed build ID; retaining it.")
            return
    except (OSError, ValueError, AttributeError):
        print("Previous site has invalid build metadata; retaining it.")
        return
    with (release / MARKER).open("x", encoding="utf-8") as output:
        json.dump({"verified_run": expected_run, "retired_at": time.time(), "web_root": str(root)}, output)
        output.write("\n")
    print("Marked verified backup for cleanup after at least one hour:", release.name)


def unchanged(release):
    """Keep backups containing extra files, symlinks, or modified build files."""
    manifest = release / ".deployment-manifest"
    if manifest.is_symlink() or not manifest.is_file():
        return False
    expected = {}
    with manifest.open(encoding="utf-8") as source:
        for line in source:
            match = re.fullmatch(r"([0-9a-f]{64})  \./([^\n]+)\n", line)
            if not match or "\\" in match.group(2):
                return False
            path = Path(match.group(2))
            if path.is_absolute() or ".." in path.parts or path.as_posix() != match.group(2):
                return False
            if path.as_posix() in expected or path.as_posix() in (MARKER, ".deployment-manifest"):
                return False
            expected[path.as_posix()] = match.group(1)
    if not expected:
        return False
    expected_dirs = set()
    for name in expected:
        expected_dirs.update(parent.as_posix() for parent in Path(name).parents if parent != Path("."))
    actual = set()
    device = release.stat().st_dev
    for directory, dirs, files in os.walk(release, followlinks=False):
        base = Path(directory)
        if any((base / name).is_symlink() for name in dirs + files):
            return False
        if any((base / name).relative_to(release).as_posix() not in expected_dirs
               or (base / name).stat().st_dev != device for name in dirs):
            return False
        for name in files:
            path = base / name
            if not path.is_file() or path.stat().st_dev != device:
                return False
            relative = path.relative_to(release).as_posix()
            if relative in (MARKER, ".deployment-manifest"):
                continue
            actual.add(relative)
            if relative not in expected:
                return False
            digest = hashlib.sha256()
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != expected[relative]:
                return False
    return actual == set(expected)


def clean(root):
    if not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError("Safe directory deletion is unavailable")
    for release in root.parent.iterdir():
        if not valid_release(root, release) or os.path.lexists(release / ".git"):
            continue
        marker = release / MARKER
        if marker.is_symlink() or not marker.is_file():
            continue
        try:
            metadata = load_json(marker)
            retired_at = metadata["retired_at"]
            if (not RUN.fullmatch(str(metadata.get("verified_run", "")))
                    or metadata.get("web_root") != str(root)
                    or not isinstance(retired_at, (int, float))
                    or not math.isfinite(retired_at)
                    or time.time() - retired_at < GRACE_SECONDS):
                continue
            if not unchanged(release):
                print("Keeping modified or unrecognized backup:", release.name)
                continue
            shutil.rmtree(release)
            print("Removed expired verified backup:", release.name)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            print("Keeping backup that could not be verified:", release.name, str(error))


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: deploy-retention.py mark ROOT RELEASE RUN | clean ROOT")
    root = web_root(sys.argv[2])
    if sys.argv[1] == "mark" and len(sys.argv) == 5:
        mark(root, Path(os.path.abspath(sys.argv[3])), sys.argv[4])
    elif sys.argv[1] == "clean" and len(sys.argv) == 3:
        clean(root)
    else:
        raise SystemExit("Invalid retention command")


if __name__ == "__main__":
    main()
