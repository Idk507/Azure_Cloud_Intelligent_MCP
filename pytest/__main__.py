from __future__ import annotations

import argparse
import pathlib
import sys
import unittest


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-q", action="store_true")
    parser.add_argument("-k", default=None)
    parser.parse_known_args()

    start_dir = pathlib.Path.cwd() / "tests"
    suite = unittest.defaultTestLoader.discover(str(start_dir), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=1)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
