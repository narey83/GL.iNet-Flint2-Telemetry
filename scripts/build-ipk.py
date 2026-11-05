#!/usr/bin/env python3
"""Build a deterministic OpenWrt/opkg package for the GL-MT6000 firmware ABI."""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import argparse

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.4.0-1"
ARCHITECTURE = "aarch64_cortex-a53"


def archive(entries):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as tar:
        directories = set()
        for name, _, _ in entries:
            directories.update(str(p) for p in Path(name).parents if str(p) != ".")
        for name in sorted(directories):
            info = tarfile.TarInfo("./" + name + "/")
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = "root"
            tar.addfile(info)
        for name, content, mode in sorted(entries):
            info = tarfile.TarInfo("./" + name)
            info.size, info.mode, info.mtime = len(content), mode, 0
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            tar.addfile(info, io.BytesIO(content))
    return gzip.compress(raw.getvalue(), mtime=0)


def build(site_config=None, ca_file=None, output_directory=None):
    entries = [("usr/share/licenses/flint2-telemetry/LICENSE", (ROOT / "LICENSE").read_bytes(), 0o644)]
    for path in sorted((ROOT / "package/files").rglob("*")):
        if path.is_file() and path.suffix not in {".crt", ".key", ".pem"}:
            relative = path.relative_to(ROOT / "package/files").as_posix()
            executable = relative.startswith(("etc/init.d/", "etc/uci-defaults/", "usr/sbin/", "usr/libexec/"))
            entries.append((relative, path.read_bytes(), 0o755 if executable else 0o644))
    capture=ROOT/"package/files/usr/sbin/flint2-capture"
    if not capture.is_file():
        raise RuntimeError("Build the ARM64 capture component with scripts/build-capture.sh first")
    binary=capture.read_bytes()
    if binary[:4]!=b"\x7fELF" or int.from_bytes(binary[18:20],"little")!=183:
        raise RuntimeError("Capture component does not match the ARM64 package architecture")
    if site_config:
        entries=[item for item in entries if item[0]!="etc/config/flint2"]
        entries.append(("etc/config/flint2",Path(site_config).read_bytes(),0o600))
    conffiles=b"/etc/config/flint2\n"
    if ca_file:
        cert=Path(ca_file).read_bytes()
        if b"-----BEGIN CERTIFICATE-----" not in cert or b"PRIVATE KEY" in cert:
            raise RuntimeError("Only a public CA certificate may be bundled")
        entries.append(("etc/flint2/collector.crt",cert,0o644))
        conffiles+=b"/etc/flint2/collector.crt\n"
    size = sum(len(content) for _, content, _ in entries)
    control = (f"Package: flint2-telemetry\nVersion: {VERSION}\nArchitecture: {ARCHITECTURE}\n"
               "Maintainer: Flint2\nSection: net\nPriority: optional\n"
               "Depends: lua, lua-cjson, luasocket, luci-lib-nixio, libuci-lua, ubus, curl, ca-bundle, jsonfilter, libstdcpp6, libgcc1, sqlite3-cli, coreutils-timeout, iptables\n"
               f"Installed-Size: {size}\nLicense: MIT, GPL-2.0-only, BSD-3-Clause, ISC\n"
               "Description: Portable router telemetry using ECS and OpenTelemetry\n")
    controls = [("control", control.encode(), 0o644),
                ("conffiles", conffiles, 0o644)]
    for name in ("postinst", "prerm"):
        controls.append((name, (ROOT / "package" / name).read_bytes(), 0o755))
    output = Path(output_directory or ROOT / "dist") / f"flint2-telemetry_{VERSION}_{ARCHITECTURE}.ipk"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(archive([("debian-binary", b"2.0\n", 0o644),
                                ("control.tar.gz", archive(controls), 0o644),
                                ("data.tar.gz", archive(entries), 0o644)]))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".ipk.sha256").write_text(f"{digest}  {output.name}\n")
    print(f"{output}: {output.stat().st_size} bytes; SHA256 {digest}")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-config",type=Path)
    parser.add_argument("--ca-file",type=Path)
    parser.add_argument("--output-directory",type=Path)
    args=parser.parse_args()
    build(args.site_config,args.ca_file,args.output_directory)
