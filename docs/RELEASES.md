# IPK builds and releases

Use [GitHub Releases](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases)
for published, persistent downloads. The **Build OpenWrt IPK** workflow compiles
pmacct/libpcap with the pinned SDK and ARM64 ring patch, then builds the generic
package from the same checkout. It does not use a binary from a maintainer's laptop.
Source checks run before compilation. Dependencies, TLS downloads and source
checksums must succeed; no fallback fixture binary is published.

The target is **GL-MT6000 vendor OpenWrt 21.02, musl, aarch64_cortex-a53,
fw3/iptables**. This package is not a universal OpenWrt IPK. Other firmware ABIs,
CPU architectures, fw4/nftables and IPv6 flow capture require separate qualification.

## Download a published release

[Release 0.3.1-6](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases/tag/v0.3.1-6)
includes the GUI export controls and direct-HTTPS setup guide. Its assets include
`flint2-telemetry_0.3.1-6_aarch64_cortex-a53.ipk` and the matching
`flint2-telemetry_0.3.1-6-sources.tar.gz`, plus checksums and Graylog imports.
Use the [latest release](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases/latest)
for future updates and read its compatibility/qualification notes.

For package-only verification, download the IPK and its matching `.ipk.sha256`
file into the same directory, then run:

```sh
sha256sum -c flint2-telemetry_0.3.1-6_aarch64_cortex-a53.ipk.sha256
# macOS alternative:
shasum -a 256 -c flint2-telemetry_0.3.1-6_aarch64_cortex-a53.ipk.sha256
```

To verify `SHA256SUMS`, download all assets named in it; otherwise the command also
reports missing files. Release notes distinguish checks performed in GitHub from
manual router qualification. A private-site profile is never part of the public
IPK: configure your own endpoints and trust before enabling it.

## Run a build

1. Open **Actions → Build OpenWrt IPK → Run workflow** and select the branch/ref.
2. Wait for the source checks, native compilation and asset preparation to finish.
3. Download the `flint2-telemetry-release` artifact from the completed run.
4. Extract it and verify `sha256sum -c SHA256SUMS` (or
   `shasum -a 256 -c SHA256SUMS` on macOS).

Manual builds do not create a public release. Their artifacts are retained for
30 days and GitHub may require sign-in to download them. Published releases give
readers persistent asset links without an Actions artifact download.

Each build includes:

- The generic `.ipk`, disabled by default with placeholder HTTPS destinations.
- The corresponding `*-sources.tar.gz`, including upstream pmacct/libpcap archives,
  source checksums, the patch, build scripts, SDK reference and licenses.
- The optional Graylog dashboard JSON and its checksum.
- `BUILD-INFO.json` with the exact source commit, target ABI and capture binary hash.
- Individual package/source checksums and `SHA256SUMS` for downloadable assets.

The SDK reference is pinned in `scripts/build-capture.sh`; the SDK itself is not
redistributed as part of the source archive. Build archives and the source manifest
make the inputs inspectable. This is not a claim of bit-identical native executables
across hosts, nor is an unsigned checksum file a signing or provenance attestation.

## Prepare and publish a version

1. Update `VERSION` in `scripts/build-ipk.py`, and `PKG_VERSION`/`PKG_RELEASE` in
   `package/Makefile`. Update installation examples and the changelog. The workflow
   rejects disagreement or a tag not equal to `v` plus the package version.
2. Commit and push. Create a tag such as `v0.3.1-6` pointing at that exact commit,
   then push the tag. The tag workflow creates a draft release only after checks
   and the fresh native build pass.
3. Download the draft assets, verify checksums and inspect `BUILD-INFO.json`.
   On a compatible router, test the built capture with `tests/capture-live.lua`,
   `tests/capture-timestamps.lua` and `tests/capture-wan.lua`. These use isolated
   loopback receivers. Supply a temporary path to the new capture binary when
   checking timestamps without installing it. Do not run probes on the same test
   receiver port concurrently. TCP flag testing uses the installed binary/config.
4. Record the actual qualification results and limitations in the release notes,
   then publish the draft. Retain all corresponding sources with the binary.
   A successful Actions run alone does not certify live router behavior.

The default build token has read-only repository access and checkout does not
persist its credentials. Only the separate tag-only draft-release job receives
`contents: write`; no long-lived release token is required. Referenced actions are
pinned to commit hashes. The workflow is not triggered with write privileges by
pull requests and never reads a private site profile, endpoint token or CA file.

For local Linux builds, use `scripts/build-capture.sh`, then
`python3 scripts/prepare-release.py` from a clean checkout. The latter refuses an
existing `dist/release` directory. Set `RELEASE_TAG` only when preparing a matching
tag. Private-site IPKs remain an explicit separate operation and must not be
uploaded as generic releases.
