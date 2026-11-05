#!/usr/bin/env python3
"""Prepare current snapshot SDK metadata for an out-of-tree source build.

SDK package-metadata.pl can emit `depends on !(A && B) || B`, making Kconfig
report a cycle through a package's own option A. The expression is always true:
conjunction A && B already implies B. Skip only positive conjunctions containing
the dependency itself. This does not disable a check or remove a constraint.
This host-side workaround is not part of the upstream package recipes.
Also relocate the SDK's absolute libtool paths, as in the legacy capture build.
"""
from pathlib import Path
import argparse

BEFORE = '\t\t\t\tnext if $dep->{"$depend if $condition"};\n'
AFTER = BEFORE + '''\t\t\t\t# A positive conjunction containing B already implies B.
\t\t\t\tnext if $condition =~ /^[A-Za-z0-9_]+(?:\\s*&&\\s*[A-Za-z0-9_]+)*$/ &&
\t\t\t\t\tgrep { $_ eq $depend } split(/\\s*&&\\s*/, $condition);
'''


def prepare(sdk):
    sdk = sdk.resolve()
    for directory in ['staging_dir', 'build_dir']:
        for archive in (sdk / directory).rglob('*.la'):
            source = archive.read_text()
            relocated = source.replace('/builder/shared-workdir/build/staging_dir/',
                                       str(sdk / 'staging_dir') + '/')
            if source != relocated:
                archive.write_text(relocated)
    path = sdk / 'scripts/package-metadata.pl'
    source = path.read_text()
    if AFTER in source:
        return
    if source.count(BEFORE) != 1:
        raise ValueError('Unrecognized SDK metadata generator; review it before applying this workaround')
    path.write_text(source.replace(BEFORE, AFTER))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdk', type=Path)
    prepare(parser.parse_args().sdk)
