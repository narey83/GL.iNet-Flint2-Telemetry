#!/usr/bin/env python3
"""Prepare a signed, target-specific opkg feed from published generic releases."""
import argparse
import gzip
import hashlib
import html
import io
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'narey83/GL.iNet-Flint2-Telemetry'
BASE_URL = 'https://narey83.github.io/GL.iNet-Flint2-Telemetry'
LANE = 'feeds/gl-mt6000/openwrt-21.02/aarch64_cortex-a53'
FEED_NAME = 'flint2_gl_mt6000_21_02'
ARCH = 'aarch64_cortex-a53'
ABI = 'OpenWrt 21.02 musl / fw3'
LABEL = 'GL-MT6000 vendor OpenWrt 21.02 / musl / fw3 only'
KEY_ID = '85cd62be71053c3e'
BOOTSTRAP_VERSION = '1.0-1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def api(path):
    return json.loads(subprocess.run(['gh', 'api', 'repos/' + REPO + path],
                                    check=True, capture_output=True, text=True).stdout)


def control_fields(raw):
    fields = {}
    current = None
    for line in raw.decode().splitlines():
        if line.startswith(' ') and current:
            fields[current] += '\n' + line
            continue
        key, sep, value = line.partition(': ')
        if not sep or not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]*', key) or key in fields:
            raise ValueError('Invalid or duplicate package control field')
        fields[key] = value
        current = key
    for key in ['Package', 'Version', 'Architecture', 'Description']:
        if not fields.get(key):
            raise ValueError('Missing control field: ' + key)
    return fields


def read_package(path):
    with tarfile.open(path, mode='r:gz') as outer:
        names = [m.name.removeprefix('./') for m in outer.getmembers()]
        if len(set(names)) != len(names):
            raise ValueError('Duplicate IPK member')
        def archive(name):
            matches = [m for m in outer if m.name.removeprefix('./') == name]
            if len(matches) != 1:
                raise ValueError('Missing IPK archive: ' + name)
            return tarfile.open(fileobj=io.BytesIO(outer.extractfile(matches[0]).read()), mode='r:gz')
        with archive('control.tar.gz') as controls, archive('data.tar.gz') as data:
            control = next(m for m in controls if m.name.removeprefix('./') == 'control')
            fields = control_fields(controls.extractfile(control).read())
            payload = {}
            for member in data:
                name = member.name.removeprefix('./')
                if member.issym() or member.islnk() or '..' in Path(name).parts or name.startswith('/'):
                    raise ValueError('Unsafe package payload member')
                if member.isfile():
                    if name in payload:
                        raise ValueError('Duplicate package payload member')
                    payload[name] = data.extractfile(member).read()
    return fields, payload


def validate_release(directory, release, expected_defaults):
    tag = release['tag_name']
    if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v\d+\.\d+\.\d+-\d+', tag):
        raise ValueError('Feed accepts only published stable version tags')
    version = tag[1:]
    package = directory / f'flint2-telemetry_{version}_{ARCH}.ipk'
    source = directory / f'flint2-telemetry_{version}-sources.tar.gz'
    sums = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9_.-]+)', line)
        if not match or match[2] in sums:
            raise ValueError('Invalid release checksum manifest')
        sums[match[2]] = match[1]
    for path in [package, source, directory / 'BUILD-INFO.json']:
        if sums.get(path.name) != digest(path):
            raise ValueError('Release checksum mismatch: ' + path.name)
    info = json.loads((directory / 'BUILD-INFO.json').read_text())
    if (info.get('version') != version or info.get('tag') != tag or info.get('architecture') != ARCH
            or info.get('firmware_abi') != ABI or info.get('site_profile_included') is not False
            or info.get('native_capture_built') is not True or not re.fullmatch(r'[a-f0-9]{40}', info.get('commit', ''))):
        raise ValueError('Release does not match the qualified feed target')
    fields, payload = read_package(package)
    if fields['Package'] != 'flint2-telemetry' or fields['Version'] != version or fields['Architecture'] != ARCH:
        raise ValueError('Package metadata mismatch')
    if payload.get('etc/config/flint2') != expected_defaults:
        raise ValueError('Feed refuses a site profile or unexpected public defaults')
    if any(name.endswith(('.crt', '.key', '.pem')) for name in payload):
        raise ValueError('Feed refuses bundled site certificates or keys')
    native = payload.get('usr/sbin/flint2-capture', b'')
    if len(native) < 65536 or native[:6] != b'\x7fELF\x02\x01' or int.from_bytes(native[18:20], 'little') != 183:
        raise ValueError('Feed requires an ELF64 AArch64 capture executable')
    if hashlib.sha256(native).hexdigest() != info.get('capture_sha256'):
        raise ValueError('Capture hash mismatch')
    # Corresponding sources must actually contain the native inputs and patch.
    with tarfile.open(source) as archive:
        names = archive.getnames()
        for suffix in ['third-party/pmacct-1.7.9.tar.gz', 'third-party/libpcap-1.11.0.tar.gz',
                       'vendor/patches/0001-nfprobe-ring-publication.patch']:
            if not any(n.endswith('/' + suffix) for n in names):
                raise ValueError('Incomplete corresponding sources')
    return package, source, fields, info


def index_entry(path, fields):
    fields = dict(fields)
    fields['Description'] = 'Flint2 community telemetry: ' + LABEL if fields['Package'] == 'flint2-telemetry' else 'Flint2 signed feed setup: ' + LABEL
    fields.update(Filename=path.name, Size=str(path.stat().st_size), SHA256sum=digest(path))
    return ''.join(k + ': ' + v + '\n' for k, v in fields.items()) + '\n'


def pad_index(data):
    # Same compatibility workaround used by OpenWrt 21.02's package/Makefile.
    return data + b'\n\n' if (64 + len(data)) % 128 in (110, 111) else data


def bootstrap(output, public_key):
    archive = runpy.run_path(str(ROOT / 'scripts/build-ipk.py'))['archive']
    config = f'src/gz {FEED_NAME} {BASE_URL}/{LANE}\n'.encode()
    preinst = br'''#!/bin/sh
[ -z "$IPKG_INSTROOT" ] || { echo 'Install feed setup on the running supported router.' >&2; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = 'glinet,gl-mt6000' ] || { echo 'Feed is only qualified for GL-MT6000.' >&2; exit 1; }
grep -q "^DISTRIB_RELEASE='21\\.02" /etc/openwrt_release || { echo 'Feed requires vendor OpenWrt 21.02.' >&2; exit 1; }
command -v fw3 >/dev/null || { echo 'Feed requires fw3/iptables.' >&2; exit 1; }
exit 0
'''
    control = (f'Package: flint2-telemetry-feed\nVersion: {BOOTSTRAP_VERSION}\nArchitecture: {ARCH}\n'
               'Maintainer: Flint2 Telemetry contributors\nSection: net\nPriority: optional\n'
               'Depends: opkg, usign\nLicense: MIT\n'
               'Description: Flint2 signed feed setup for GL-MT6000 vendor OpenWrt 21.02 / fw3 only\n').encode()
    entries = [('etc/opkg/flint2-telemetry.conf', config, 0o644),
               ('etc/opkg/keys/' + KEY_ID, public_key.read_bytes(), 0o644),
               ('usr/share/licenses/flint2-telemetry-feed/LICENSE', (ROOT / 'LICENSE').read_bytes(), 0o644)]
    controls = [('control', control, 0o644), ('conffiles', b'/etc/opkg/flint2-telemetry.conf\n', 0o644),
                ('preinst', preinst, 0o755)]
    path = output / f'flint2-telemetry-feed_{BOOTSTRAP_VERSION}_{ARCH}.ipk'
    path.write_bytes(archive([('debian-binary', b'2.0\n', 0o644),
                              ('control.tar.gz', archive(controls), 0o644), ('data.tar.gz', archive(entries), 0o644)]))
    path.with_suffix('.ipk.sha256').write_text(digest(path) + '  ' + path.name + '\n')
    return path, control_fields(control)


def render_landing(info, setup, public_key):
    capabilities = json.loads((ROOT / 'feed/dashboard-capabilities.json').read_text())
    dashboard_rows = ''.join('<tr><th>' + html.escape(d['name']) + '</th><td>' + str(d['widgets']) + '</td><td>' + html.escape(d['capability']) + '</td></tr>' for d in capabilities)
    return ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flint2 community signed package feed</title><style>body{font:18px/1.6 system-ui;max-width:850px;margin:3rem auto;padding:0 1rem}code{overflow-wrap:anywhere}table{border-collapse:collapse}td,th{text-align:left;vertical-align:top;padding:.6rem;border-bottom:1px solid #ddd}</style>
<h1>Flint2 community signed package feed</h1>
<p><strong>Only qualified for ''' + html.escape(LABEL) + ''' (aarch64_cortex-a53).</strong>
Not an official OpenWrt feed. Not qualified for stock newer OpenWrt, fw4/nftables, APK or other routers.</p>
<p>Current telemetry package: ''' + html.escape(info['version']) + '''.</p>
<h2>Set up through LuCI</h2><ol><li>Download <a href="''' + setup.name + '''">the feed setup IPK</a>
and <a href="''' + setup.name + '''.sha256">its checksum</a>.</li>
<li>In LuCI, open System → Software → Upload Package and install the setup IPK.</li>
<li>Click Update lists, search for <code>flint2-telemetry</code>, then install it.
Future published versions appear after updating lists.</li></ol>
<p>The setup package installs this feed address and its public verification key. It does not start telemetry.
Review the <a href="https://github.com/''' + REPO + '''/blob/main/docs/FEED.md">compatibility, trust and removal guide</a> first.</p>
<h2>What the dashboards help you investigate</h2>
<p>The optional Graylog import includes 10 dashboards, 13 pages and 183 widgets.
The agent also exports ECS and OpenTelemetry data for other compatible platforms.</p>
<table><thead><tr><th>Dashboard</th><th>Widgets</th><th>Capabilities</th></tr></thead><tbody>''' + dashboard_rows + '''</tbody></table>
<p><a href="flint2-dashboards.json">Download the native dashboard content pack</a> ·
<a href="flint2-dashboards.json.sha256">Checksum</a> ·
<a href="https://github.com/''' + REPO + '''/blob/main/docs/integrations/GRAYLOG.md">Setup and import guide</a> ·
<a href="https://github.com/''' + REPO + '''/blob/main/docs/integrations/GRAYLOG-DASHBOARDS.md">Full catalogue and enrichment requirements</a></p>
<p>Enable metric log copies for metric charts. Maps/ASN and intelligence panels need your own enrichment.
VPN observations are forwarded attempts, not WireGuard handshakes or confirmed connections.
SYN/volume indicators are not confirmed attacks; device inventory is not proof a device is online.
Flow observations can overlap and are not lossless accounting.</p>
<h2>Trust identity</h2><p>usign key fingerprint: <code>''' + KEY_ID + '''</code><br>
Public-key SHA-256: <code>''' + digest(public_key) + '''</code><br>
Setup IPK SHA-256: <code>''' + digest(setup) + '''</code></p>
<p><a href="flint2-telemetry.pub">Public key</a> · <a href="''' + LANE + '''/Packages">Signed package index</a> ·
<a href="''' + LANE + '''/Packages.sig">Signature</a> · <a href="https://github.com/''' + REPO + '''/releases">Releases and qualification</a></p>
<p>Native IPKs and matching source archives are hosted together in <code>''' + LANE + '''</code>.
The feed retains up to 20 published stable versions; the index offers only the current version and feed setup package.
Packages start disabled and need your own HTTPS destination settings.</p></html>''')


def publish(output, secret_key, usign):
    public_key = ROOT / 'feed/keys/flint2-telemetry.pub'
    fingerprint = subprocess.run([usign, '-F', '-p', str(public_key)], check=True, capture_output=True, text=True).stdout.strip()
    if fingerprint != KEY_ID:
        raise ValueError('Public key fingerprint mismatch')
    if output.exists():
        raise ValueError('Use a fresh feed output directory')
    output.mkdir(parents=True)
    lane = output / LANE
    lane.mkdir(parents=True)
    downloads = ROOT / 'dist/feed-downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    latest = api('/releases/latest')
    releases = [latest] + [r for r in api('/releases?per_page=100')
                           if not r['draft'] and not r['prerelease'] and r['id'] != latest['id']][:19]
    selected = None
    for release in releases:
        tag = release['tag_name']
        if not re.fullmatch(r'v\d+\.\d+\.\d+-\d+', tag):
            if release == latest:
                raise ValueError('Unsupported latest stable release tag')
            continue
        directory = downloads / tag
        directory.mkdir(exist_ok=False)
        subprocess.run(['gh', 'release', 'download', tag, '--repo', REPO, '--dir', str(directory),
                        '--pattern', '*.ipk', '--pattern', '*-sources.tar.gz', '--pattern', 'SHA256SUMS',
                        '--pattern', 'BUILD-INFO.json', '--pattern', 'flint2-dashboards.json',
                        '--pattern', 'flint2-dashboards.json.sha256'], check=True)
        package, source, fields, info = validate_release(directory, release, (ROOT / 'package/files/etc/config/flint2').read_bytes())
        if api('/commits/' + tag)['sha'] != info['commit']:
            raise ValueError('Release metadata commit differs from the published tag')
        for path in [package, source]:
            shutil.copyfile(path, lane / path.name)
        if release == latest:
            sums = dict((line.split('  ', 1)[1], line.split('  ', 1)[0]) for line in (directory / 'SHA256SUMS').read_text().splitlines())
            for name in ['flint2-dashboards.json', 'flint2-dashboards.json.sha256']:
                if sums.get(name) != digest(directory / name):
                    raise ValueError('Dashboard asset checksum mismatch')
                shutil.copyfile(directory / name, output / name)
            selected = lane / package.name, fields, info
    setup, setup_fields = bootstrap(output, public_key)
    shutil.copyfile(setup, lane / setup.name)
    package, fields, info = selected
    index = pad_index((index_entry(package, fields) + index_entry(lane / setup.name, setup_fields)).encode())
    (lane / 'Packages').write_bytes(index)
    (lane / 'Packages.gz').write_bytes(gzip.compress(index, mtime=0))
    subprocess.run([usign, '-S', '-s', str(secret_key), '-m', str(lane / 'Packages'), '-x', str(lane / 'Packages.sig')], check=True)
    subprocess.run([usign, '-V', '-p', str(public_key), '-m', str(lane / 'Packages'), '-x', str(lane / 'Packages.sig')], check=True)
    shutil.copyfile(public_key, output / 'flint2-telemetry.pub')
    state = {'feed': FEED_NAME, 'label': LABEL, 'architecture': ARCH, 'firmware_abi': ABI,
             'latest_version': info['version'], 'source_commit': info['commit'], 'key_fingerprint': KEY_ID,
             'public_key_sha256': digest(public_key), 'bootstrap_sha256': digest(setup),
             'feed_url': BASE_URL + '/' + LANE, 'bootstrap': setup.name}
    (output / 'feed-info.json').write_text(json.dumps(state, indent=2) + '\n')
    (output / '.nojekyll').write_text('')
    (output / 'index.html').write_text(render_landing(info, setup, public_key))
    print(json.dumps(state, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/site')
    parser.add_argument('--secret-key', type=Path, required=True)
    parser.add_argument('--usign', default=str(ROOT / 'vendor/.cache/usign'))
    args = parser.parse_args()
    publish(args.output, args.secret_key, args.usign)
