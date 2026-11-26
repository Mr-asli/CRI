"""Command-line utilities for local CRI audit verification."""
import argparse
import json
import os
from pathlib import Path

from .core import Audit


def main() -> int:
    parser = argparse.ArgumentParser(prog='cri-audit')
    subparsers = parser.add_subparsers(dest='command', required=True)
    verify = subparsers.add_parser('verify', help='verify the local JSONL audit hash chain')
    verify.add_argument('--file', default=os.getenv('CRI_AUDIT_FILE', './data/audit.jsonl'))
    args = parser.parse_args()
    if args.command == 'verify':
        result = Audit(Path(args.file)).verify()
        print(json.dumps(result, sort_keys=True))
        return 0 if result['valid'] else 1
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
