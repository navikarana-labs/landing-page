#!/usr/bin/env python3
"""Atomically exchange a staged site with the live document root on Linux."""

import ctypes
import os
import re
import sys


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: deploy-exchange.py WEB_ROOT STAGE")
    root, stage = map(os.path.abspath, sys.argv[1:])
    if (root == os.path.dirname(root)
            or os.path.dirname(root) != os.path.dirname(stage)
            or not re.fullmatch(r"\.navikarana-release-[0-9]+-[0-9]+", os.path.basename(stage))
            or root == stage):
        raise SystemExit("Unsafe deployment paths")
    for path in (root, stage):
        if os.path.islink(path) or not os.path.isdir(path):
            raise SystemExit("Both deployment paths must be real directories")
    if os.stat(root).st_dev != os.stat(stage).st_dev:
        raise SystemExit("Live and staged directories must share a filesystem")
    for name in ("index.html", "404.html", ".htaccess", "deployment-version.json", ".deployment-manifest"):
        if not os.path.isfile(os.path.join(stage, name)):
            raise SystemExit(f"Missing staged file: {name}")
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = libc.renameat2
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    if renameat2(-100, os.fsencode(root), -100, os.fsencode(stage), 2) != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))
    print("Exchange complete. Previous site retained in", stage)


if __name__ == "__main__":
    main()
