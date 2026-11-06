# Official OpenWrt repository preparation

Status: **technical candidate qualified for maintainer review**. Human review and
genuine DCO sign-offs remain required before upstream submission. The community
feed remains the install/update route for the qualified GL-MT6000 vendor 21.02
firmware. No upstream pull request has been submitted and the project is not in
the default OpenWrt repositories.

Maintainer: **John Narey <john.narey@gmail.com>**. This public identity is recorded
in `package/Makefile`. A metadata-only maintainer change does not require a
package release increment under the packages contribution guidelines. It does
not replace or rebuild the published 0.3.1-6 assets.

## Intended submissions

Submit new packages against the current development branches, after qualification.
Default repository inclusion is a source-package review; it does not register our
GitHub Pages feed or approve our existing vendor-firmware IPK for other firmware.

| Proposed package | Destination | Source ownership |
| --- | --- | --- |
| `flint2-telemetry` | `openwrt/packages`, `net/flint2-telemetry` | Lua agent/modules, UCI defaults, procd service and firewall integration |
| `flint2-capture` | `openwrt/packages`, `net/flint2-capture` (subject to review of an upstream pmacct package instead) | Source-built pmacct capture component, local patch and required license notices |
| `luci-app-flint2-telemetry` | `openwrt/luci`, `applications/luci-app-flint2-telemetry` | JavaScript view, menu and rpcd ACL; depends on the backend package |

The names and split are proposals, not accepted upstream package names. The
backend must install without LuCI. The UI package must own only its view, menu
and ACL, avoiding file collisions with the backend. Optional Graylog imports stay
in this project's releases/docs rather than becoming router dependencies.

Current paths to split:

- Backend: `package/files/usr/sbin/flint2-agent`, `usr/lib/lua/flint2/`,
  `etc/config/flint2`, `etc/init.d/flint2`, `usr/libexec/flint2/`.
- UI: `package/files/www/luci-static/resources/view/flint2/`,
  `usr/share/luci/menu.d/`, `usr/share/rpcd/acl.d/`.
- Capture: build from upstream sources and install as `/usr/sbin/flint2-capture`;
  do not copy the ignored binary from a developer checkout.
- Keep the current vendor-feed package intact until a separately qualified
  replacement is available. Migration from its combined file ownership to the
  split packages needs an explicit upgrade test.

## Implementation and qualification

The 0.4.0 candidate is on the `openwrt-current` branch. See
[current OpenWrt builds](OPENWRT-CURRENT.md) for build/install instructions and
precise scope. The public vendor feed remains on its qualified release.

| Area | Candidate implementation | Qualification |
| --- | --- | --- |
| Backend dependencies | `openwrt/flint2-telemetry/Makefile` uses core/packages dependencies, LuaPOSIX and a separate capture package | Platform checks and transport fixtures run on current OpenWrt without nixio; vendor nixio fallback tested separately |
| Source builds | Capture builds with the selected SDK toolchain and OpenWrt libpcap; backend uses a full-commit/SHA-256 source pin | Complete x86-64 and MediaTek/Filogic builds passed, including the final standalone LuCI package |
| Firewall | fw4 JSON transactions preserve the deny rules' matches; fw3 path retained for vendor builds | Real fw4 reload, cleanup, idempotency, constrained deny rules and failure cases passed in an isolated OpenWrt system |
| Architecture | Native package restricted to 64-bit; service queries the compiled record layout | x86-64 query and live loopback flags/timestamps tested; Filogic hardware/offload behavior is not certified by a cross-build |
| Package ownership | Backend, native capture and LuCI own separate paths | Signed install, disabled defaults, headless backend, upgrade/config retention, container restart, license notices and removal passed; cross-ABI migration is not supported |
| CLI | Agent `--help`/`--version` run before modules/config; unknown options exit 2 | CI probes and explicit package version test avoid invoking firewall helpers |
| Native patches | Refreshed through OpenWrt quilt targets; provenance headers and upstream status included | Human review and genuine DCO sign-offs still required; no sign-off has been created on your behalf |
| Licenses | MIT backend/UI; capture retains pmacct and bundled libcdada notices, with system libpcap | Maintainer must review final source/license obligations before signing |

The source recipes are under `openwrt/`. The older `package/Makefile` and Python
IPK builder remain the combined vendor-firmware build path; they are not the
recipes to copy into the official repositories. SDK preparation workarounds are
host tooling, not patches to an installed router or requirements imposed by the
package recipes.

## Source baseline

The current backend recipe pins commit
`853002997d73ca820703b09c8a590a285651e59f`, archive SHA-256
`6b026094d455f5fb72be81ca479e52fb0f07be62d775a3debcc5f973a70c9206`.
Its runtime is checked against the tested tree. Native capture uses its own
upstream source pin and refreshed patches in `openwrt/flint2-capture/`.

The last qualified release is `v0.3.1-6`, from source commit
`b5d202b86cfb896b9433ba2c3d27898adcf28e12`. Its matching
[source bundle](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases/download/v0.3.1-6/flint2-telemetry_0.3.1-6-sources.tar.gz)
has SHA-256 `0a49896f089f29f94fca72d9cb065e390498dc6e2b7b82cce578a33a9a54a347`
(release asset metadata checked during preparation). This is the legacy baseline,
not the future current-OpenWrt submission version.

Its native source inputs are pinned in `scripts/build-capture.sh`:

| Input | SHA-256 |
| --- | --- |
| pmacct 1.7.9 | `94185c33d659772035c63be0a82601bb9eb064fb4be1d68ba279b47204b2750a` |
| libpcap 1.11.0 | `596389bc8560ea027dff9db8aaf6c173d992366d9aef4baf5d7c6d180b4d49ad` |

An upstream recipe should normally use OpenWrt's libpcap package rather than
privately rebuilding it. Any resulting native behavior/layout changes need fresh
flow and timestamp tests. Publish a new immutable source release containing the
port before pinning its archive and hash in the submission.

## Review checklist

- [ ] Read the final branch diff and `VALIDATION.md`, including build-workaround
  evidence and the limits of container tests versus physical Filogic hardware.
- [ ] Confirm source/version/hash pins, installed file ownership, licenses and
  maintained dependency versions against the destination repositories.
- [ ] Review the native publication patch and decide its upstream submission
  route; review the two distribution integration patches.
- [ ] Refresh patches with `make package/flint2-capture/prepare QUILT=1` and
  `make package/flint2-capture/refresh` after any further native changes.
- [ ] Add genuine author/DCO sign-offs after reviewing the source obligations.
- [ ] Write/review the short upstream descriptions, disclosing AI assistance and
  quoting only actual build/runtime results.

## Human submission handoff

The packages repository requires AI assistance disclosure and human review, and
says: **“Do not use autonomous agents for contributing to our projects.”** This
preparation does not create an upstream PR, post comments, or certify a DCO
sign-off on the maintainer's behalf. John must understand and review the finished
port and submit it personally under those rules.

Suggested titles after the implementation and testing are complete:

- `flint2-telemetry: add structured router telemetry agent`
- `flint2-capture: add flow capture component` (if a separate package is agreed)
- `luci-app-flint2-telemetry: add telemetry configuration`

Write a short description in your own words covering the function, source
release, dependency/split choices and **actual** current-target test results.
Disclose AI assistance in preparation/development and your review of that work.
Do not claim any unchecked qualification item passed. Add your own sign-off only
after reviewing the [Developer Certificate of Origin](https://developercertificate.org/).

Requirements checked on 2026-11-05:

- [Packages contribution rules](https://github.com/openwrt/packages/blob/1d995816576cf8a10194ef8bb39b626c0d437cd0/CONTRIBUTING.md)
  (AI policy, dependencies, builds, sources, patch format and maintainer/sign-off).
- [LuCI contribution rules](https://github.com/openwrt/luci/blob/2cd0c0bd04cf2e82f9425199b4da87aaae6f103a/CONTRIBUTING.md)
  (component naming, current development branch and sign-off).

Recheck the live contribution rules before submission. Acceptance and the firmware
branches/targets that ship a package are decided by OpenWrt maintainers. Inclusion
would make it available in configured default feeds for the applicable builds;
it would not retrofit old vendor firmware or install it automatically.
