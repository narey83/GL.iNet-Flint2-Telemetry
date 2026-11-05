#!/bin/sh
set -eu
/usr/sbin/flint2-capture -V
size=$(/usr/sbin/flint2-capture --flint2-buffer-size)
case "$size" in ''|*[!0-9]*) exit 1 ;; esac
[ "$size" -ge 64 ] && [ "$size" -le 4096 ]
