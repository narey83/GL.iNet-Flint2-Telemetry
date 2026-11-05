#!/usr/bin/env python3
"""Prepare generic release assets from a compiled capture binary; never publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def check_version(root=ROOT, tag=''):
    builder = runpy.run_path(str(root / 'scripts/build-ipk.py'))
    version = builder['VERSION']
    makefile = (root / 'package/Makefile').read_text()
    upstream = re.search(r'^PKG_VERSION:=(.+)$', makefile, re.M).group(1)
    revision = re.search(r'^PKG_RELEASE:=(.+)$', makefile, re.M).group(1)
    if version != upstream + '-' + revision:
        raise ValueError('Package builder and Makefile versions differ')
    if tag and tag != 'v' + version:
        raise ValueError('Release tag must be v' + version)
    return builder


def prepare(root=ROOT, tag=''):
    builder = check_version(root, tag)
    binary = root / 'package/files/usr/sbin/flint2-capture'
    # Do not mistake a packaging-test ELF header for a real release executable.
    elf = binary.read_bytes()
    if len(elf) < 65536 or elf[:6] != b'\x7fELF\x02\x01' or int.from_bytes(elf[18:20], 'little') != 183:
        raise ValueError('Release requires a compiled ELF64 little-endian AArch64 capture executable')
    status = subprocess.run(['git', 'status', '--porcelain'], cwd=root, check=True,
                            capture_output=True, text=True).stdout
    if status:
        raise ValueError('Release requires a clean source checkout')
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, check=True,
                            capture_output=True, text=True).stdout.strip()
    dynamic = subprocess.run(['readelf', '-d', str(binary)], check=True,
                             capture_output=True, text=True).stdout
    libraries = set(re.findall(r'\(NEEDED\).*?\[([^]]+)\]', dynamic))
    if not libraries or libraries - {'libc.so', 'libgcc_s.so.1', 'libstdc++.so.6'}:
        raise ValueError('Unexpected capture runtime libraries: ' + repr(sorted(libraries)))
    output = root / 'dist/release'
    if output.exists():
        raise ValueError('Release output already exists; use a fresh checkout or remove dist/release')
    output.mkdir(parents=True)
    # No site-config/CA arguments: a release always uses the generic disabled profile.
    builder['build'](output_directory=output)
    bundle = runpy.run_path(str(root / 'scripts/bundle-sources.py'))
    source = output / ('flint2-telemetry_' + builder['VERSION'] + '-sources.tar.gz')
    bundle['bundle'](root / 'vendor/.cache', source)
    for name in ['flint2-dashboards.json', 'flint2-dashboards.json.sha256']:
        shutil.copyfile(root / 'integrations/graylog' / name, output / name)
    metadata = {'version': builder['VERSION'], 'architecture': builder['ARCHITECTURE'],
                'commit': commit, 'tag': tag or None, 'firmware_abi': 'OpenWrt 21.02 musl / fw3',
                'capture_sha256': hashlib.sha256(elf).hexdigest(), 'runtime_libraries': sorted(libraries),
                'site_profile_included': False, 'native_capture_built': True,
                'live_router_tests': 'Not run by GitHub Actions; see release notes for manual qualification.'}
    (output / 'BUILD-INFO.json').write_text(json.dumps(metadata, indent=2) + '\n')
    (output / 'RELEASE-NOTES.md').write_text(
        '# GL.iNet Flint2 Telemetry ' + builder['VERSION'] + '\n\n'
        'Generic package for the GL-MT6000 vendor OpenWrt 21.02 ABI '
        '(`aarch64_cortex-a53`, musl, fw3/iptables). Other firmware/CPU ABIs are not qualified.\n\n'
        'Built from the tagged source with checksum-pinned SDK, pmacct/libpcap sources '
        'and the ARM64 capture synchronization patch. Source/contract checks run in CI; '
        'CI does not certify router traffic or hardware acceleration behavior.\n\n'
        'The IPK starts disabled, with placeholder HTTPS endpoints and system CA trust. '
        'No home addresses, credentials or private certificates are included. '
        'Configure your own destination before enabling it. Reinstall after firmware '
        'upgrades if the firmware removes installed packages.\n\n'
        'Includes the corresponding source bundle, SHA256SUMS, build commit/ABI metadata '
        'and the optional Graylog content pack (10 dashboards / 183 widgets). '
        'Keep the source bundle with redistributed binaries.\n\n'
        '[Setup and compatibility](https://github.com/narey83/GL.iNet-Flint2-Telemetry#readme) · '
        '[Graylog setup/imports](https://github.com/narey83/GL.iNet-Flint2-Telemetry/blob/main/docs/integrations/GRAYLOG.md)\n')
    assets = [p for p in sorted(output.iterdir()) if p.is_file() and p.name != 'RELEASE-NOTES.md']
    (output / 'SHA256SUMS').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in assets))
    print('Prepared release assets in ' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-version', action='store_true')
    args = parser.parse_args()
    tag = os.environ.get('RELEASE_TAG', '')
    if args.check_version:
        check_version(tag=tag)
    else:
        prepare(tag=tag)
