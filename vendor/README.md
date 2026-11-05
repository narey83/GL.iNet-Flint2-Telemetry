# Capture component provenance

Native capture is pmacct 1.7.9 (`pmacctd`, renamed `flint2-capture`), with libpcap
1.11.0 and the release's bundled libcdada 0.6. Source URLs and SHA-256 values are
pinned in `scripts/build-capture.sh`. The local patch in `vendor/patches/` synchronizes shared-memory publication
between the capture core and nfprobe on ARM64. The build also relocates the SDK's
absolute libtool metadata paths. Upstream source archives remain unchanged.

Licenses: pmacct GPL-2.0 with additional ISC-covered material, libpcap BSD and
libcdada BSD-3-Clause. Full upstream notices are bundled in
`package/files/usr/share/licenses/flint2-capture/THIRD-PARTY-LICENSES`.
The Flint2 agent's MIT license does not replace those licenses.

For a binary distribution, retain the exact downloaded source tarballs, build
script, checksums and notices beside the release. Supply the corresponding SDK
reference/configuration and any changes. The source archives in `vendor/.cache/`
are build inputs, not committed binary blobs. Review upstream security advisories
before promoting a release; these pinned legacy-ABI components are not a guarantee
of support or freedom from vulnerabilities.
