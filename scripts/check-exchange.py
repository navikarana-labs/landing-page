#!/usr/bin/env python3
"""Test Linux directory exchange in an isolated sibling of the document root."""

import ctypes
import os
import sys
import tempfile
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check-exchange.py WEB_ROOT")
    root = Path(os.path.abspath(sys.argv[1]))
    if root == root.parent or root.is_symlink() or not root.is_dir():
        raise SystemExit("The document root must be a real directory")
    if os.stat(root).st_dev != os.stat(root.parent).st_dev:
        raise SystemExit("The document root and its parent must share a filesystem")
    with tempfile.TemporaryDirectory(prefix=".navikarana-exchange-test-", dir=root.parent) as temp:
        first = Path(temp) / "first"
        second = Path(temp) / "second"
        first.mkdir()
        second.mkdir()
        (first / "identity").write_text("first", encoding="utf-8")
        (second / "identity").write_text("second", encoding="utf-8")
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        if renameat2(-100, os.fsencode(first), -100, os.fsencode(second), 2) != 0:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))
        if ((first / "identity").read_text(encoding="utf-8") != "second"
                or (second / "identity").read_text(encoding="utf-8") != "first"):
            raise RuntimeError("Directory exchange did not produce the expected result")
    print("Isolated directory exchange succeeded; live site was not modified.")


if __name__ == "__main__":
    main()
