#!/usr/bin/env sh
# Internal helper: builds a verified WORK-IN-PROGRESS snapshot only.
# It never labels an incomplete tree as a final release.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
OUT="${1:-$ROOT/../cri-work-in-progress.zip}"
python - "$ROOT" "$OUT" <<'PY'
from pathlib import Path
import hashlib, sys, zipfile
root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
excluded_dirs = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'dist', 'build', 'data', 'artifacts'}
excluded_suffixes = {'.pyc', '.log', '.sqlite', '.sqlite3', '.db'}
excluded_files = {'.coverage', 'MANIFEST.md'}
files = []
for p in root.rglob('*'):
    if not p.is_file():
        continue
    rel = p.relative_to(root)
    if any(part in excluded_dirs for part in rel.parts):
        continue
    if p.name == '.env' or (p.name.startswith('.env.') and p.name != '.env.example'):
        continue
    if p.name in excluded_files or p.name == '.DS_Store' or p.suffix in excluded_suffixes:
        continue
    if p == out:
        continue
    files.append(p)
files.sort()
manifest = root / 'MANIFEST.md'
lines = ['# CRI Manifest', '', 'This is the exact file inventory included in the work-in-progress archive.', '', f'File count: {len(files) + 1}', '']
for p in files:
    rel = p.relative_to(root).as_posix()
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    lines.append(f'- `{rel}` — SHA-256 `{digest}`')
manifest.write_text('\n'.join(lines) + '\n', encoding='utf-8')
files.append(manifest)
files.sort()
out.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for p in files:
        zf.write(p, Path('cri') / p.relative_to(root))
with zipfile.ZipFile(out) as zf:
    bad = zf.testzip()
    if bad:
        raise SystemExit(f'ZIP CRC failure: {bad}')
    names = set(zf.namelist())
    expected = {str(Path('cri') / p.relative_to(root)).replace('\\', '/') for p in files}
    if names != expected:
        raise SystemExit(f'ZIP inventory mismatch: missing={expected-names}, extra={names-expected}')
print(f'Created work-in-progress archive: {out}')
print(f'Files: {len(files)}; bytes: {out.stat().st_size}')
PY
