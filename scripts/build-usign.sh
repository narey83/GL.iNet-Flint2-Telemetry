#!/bin/sh
# Build the official OpenWrt usign tool from checksum-pinned source.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
cache="$root/vendor/.cache"
revision=c4c72b1b07945ee192361dc751291a7c98d6adcd
mkdir -p "$cache"
if [ ! -f "$cache/usign-source.tar.gz" ]; then
    curl --fail --location --proto '=https' --tlsv1.2 \
        "https://codeload.github.com/openwrt/usign/tar.gz/$revision" -o "$cache/usign-source.tar.gz"
fi
python3 - "$cache/usign-source.tar.gz" <<'PY'
import hashlib,sys
from pathlib import Path
assert hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest() == 'd647f4978f56a159fe29c6888fadb1c008d0be52168c3215338f14bc47a3ae25', 'usign source checksum mismatch'
PY
tar -xzf "$cache/usign-source.tar.gz" -C "$cache"
source_dir="$cache/usign-$revision"
cc -O2 -Wall -Werror -std=gnu99 -Wmissing-declarations -o "$cache/usign" \
    "$source_dir/ed25519.c" "$source_dir/edsign.c" "$source_dir/f25519.c" \
    "$source_dir/fprime.c" "$source_dir/sha512.c" "$source_dir/main.c" "$source_dir/base64.c"
