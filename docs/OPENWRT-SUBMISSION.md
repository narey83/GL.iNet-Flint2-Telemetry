# Official OpenWrt repository preparation

Status: **preparation only; not ready for upstream submission**. The community
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

## Readiness gaps

| Requirement | Current evidence | Work before submission |
| --- | --- | --- |
| Current development OpenWrt | Existing builds/runtime evidence target vendor 21.02, musl, Cortex-A53 | Build and run on current development OpenWrt; record exact SDK/build revision and device/image |
| Native source build | `scripts/build-capture.sh` downloads a fixed 21.02 SDK; `package/Makefile` has an empty compile step | Use OpenWrt's selected cross toolchain, configure/package infrastructure and checksum-pinned sources; no SDK download inside the recipe |
| Backend dependencies | Agent imports `nixio`; `luci-lib-nixio` belongs to the LuCI feed | Replace its signal/file-metadata uses with a supported core/packages dependency, preserving SIGTERM and credential-file ownership/permission checks |
| Firewall backend | Helper hooks fw3/iptables chains, including `zone_wan_src_DROP` | Add and test fw4/nftables observation hooks and cleanup; never change accept/drop policy; preserve or explicitly scope legacy support |
| Architecture scope | Capture ABI/buffer size and binary validation are qualified only for A53 | Derive/verify layout with the selected target or restrict support to the architectures actually tested; do not mark the native package `all` |
| Clean installation | Private site installation and vendor-ABI tests exist | Test disabled public defaults, configure through LuCI, enable/restart/reload, remove and upgrade on the intended upstream image |
| Patch submission | ARM64 ring fix exists in `vendor/patches/` | Review ownership and upstream status; prepare required mail header and genuine author sign-off, then refresh using OpenWrt quilt targets |
| License declarations | MIT agent and bundled third-party notices exist | Confirm SPDX expressions and license files against each selected upstream release, including bundled libcdada; preserve all applicable notices |
| CLI/CI safety | Agent has `--check-config`, but no `--version`/`--help` handling | Add side-effect-free informational flags or an appropriate upstream functional test; CI probes must not start collection |
| Dependency/security review | Legacy source versions are pinned | Review maintained upstream versions, advisories and required dependency names against the selected current feed revisions |

Do not submit the existing `package/Makefile` as an official recipe: it installs
an externally built asset and combines backend/UI files. Do not add an untested
recipe with invented hashes or declare modern firmware support from legacy tests.
This preparation deliberately records the gaps rather than presenting such a
recipe as ready to merge.

## Source baseline

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

## Qualification checklist

Record results, commands, versions and limitations in `VALIDATION.md`; unchecked
items below are required work, not test results.

- [ ] Clean source download, prepare and compile through OpenWrt buildroot/SDK;
  resolve all dependencies from core/packages for the backend.
- [ ] Confirm source/license manifests and generated package metadata; no private
  endpoints, headers, certificates, signing keys or binaries in the source archive.
- [ ] Run the existing Python, Lua, LuCI and shell checks from
  `.github/workflows/checks.yml` against the port, plus appropriate static checks.
- [ ] Refresh native patches with `make package/flint2-capture/refresh` after
  `make package/flint2-capture/{clean,prepare} QUILT=1` in the selected buildroot;
  review any changed source/layout assumptions.
- [ ] On current OpenWrt, verify signal handling, protected header-file checks,
  TLS verification/failure behavior and exporter self-observations.
- [ ] Verify OTLP logs/metrics, ECS NDJSON and GELF against compatible receivers;
  include malformed configuration and destination outage cases.
- [ ] Exercise WAN/LAN and configured VPN/interface capture, TCP flags and flow
  timestamp handling using bounded fixtures/live traffic; document offload limits.
- [ ] Verify fw4 hook reload/idempotency/removal, rate limits and unchanged packet
  policy before/after installation, restart and package removal.
- [ ] Test LuCI controls/ACLs, disabled clean install, config preservation during
  upgrade, split-package ownership migration and removal with no orphan hooks.
- [ ] Add upstream package tests appropriate to its current CI; test informational
  CLI flags without accessing router hardware or sending telemetry.
- [ ] Have the maintainer review the complete diff and source/license obligations;
  then create genuine author/DCO sign-offs and human-reviewed submission text.

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
