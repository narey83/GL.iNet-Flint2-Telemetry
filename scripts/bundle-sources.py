#!/usr/bin/env python3
"""Prepare the matching public source bundle for a binary release; never publish it."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    'pmacct-1.7.9.tar.gz': '94185c33d659772035c63be0a82601bb9eb064fb4be1d68ba279b47204b2750a',
    'libpcap-1.11.0.tar.gz': '596389bc8560ea027dff9db8aaf6c173d992366d9aef4baf5d7c6d180b4d49ad',
}


def public_files(root):
    for name in ['LICENSE', 'README.md', 'ROADMAP.md', 'VALIDATION.md', 'CHANGELOG.md', '.gitignore']:
        yield root / name
    for directory in ['docs', 'integrations', 'scripts', 'tests', 'package', 'deploy', '.github', 'vendor/patches']:
        for path in sorted((root / directory).rglob('*')):
            if not path.is_file() or path.is_symlink() or '__pycache__' in path.parts:
                continue
            if path.name == 'flint2-capture' or path.suffix in {'.pyc', '.crt', '.pem', '.key'}:
                continue
            yield path
    yield root / 'vendor/README.md'


def bundle(cache, output):
    entries = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in public_files(ROOT)}
    for name, digest in SOURCES.items():
        source = (cache / name).read_bytes()
        if hashlib.sha256(source).hexdigest() != digest:
            raise ValueError('Source checksum mismatch: ' + name)
        entries['third-party/' + name] = source
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.GNU_FORMAT) as archive:
        for name, content in sorted(entries.items()):
            info = tarfile.TarInfo('flint2-telemetry-0.3.1/' + name)
            info.size = len(content)
            info.mode = 0o755 if name.endswith('.sh') else 0o644
            info.uid = info.gid = info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(gzip.compress(raw.getvalue(), mtime=0))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(digest + '  ' + output.name + '\n')
    print(f'Prepared {output}: {len(entries)} source entries, SHA256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-cache', type=Path, default=ROOT / 'vendor/.cache')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/flint2-telemetry_0.3.1-sources.tar.gz')
    args = parser.parse_args()
    bundle(args.vendor_cache, args.output)
