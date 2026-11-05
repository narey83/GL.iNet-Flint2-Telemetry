# Current OpenWrt source packages

The 0.4.0 development candidate separates the agent, capture binary and LuCI UI.
The existing signed community feed still serves the qualified vendor 21.02 IPK;
these new source recipes do not change that feed or upgrade a router's firmware.

| Package | Contents | Dependencies |
| --- | --- | --- |
| `flint2-telemetry` | Lua agent, UCI configuration, procd service and firewall observation hooks | Core/packages feed only: Lua, cjson, LuaSocket, LuaPOSIX, UCI, ubus, curl, CA bundle, jsonfilter, timeout, fw4 and capture |
| `flint2-capture` | Source-built pmacct 1.7.9 with publication/layout patches | OpenWrt libpcap and libstdc++; currently restricted to 64-bit targets |
| `luci-app-flint2-telemetry` | Services → Flint2 Telemetry, menu and restricted rpcd ACL | Agent and LuCI base |

There is no backend dependency on `luci-lib-nixio` or sqlite3. LuaPOSIX handles
signals and private-header-file checks. The vendor package can still use nixio;
its optional GL.iNet client database enrichment requires sqlite3 if that database
exists. The backend works without the UI.

## Source builds

Use a Linux x86-64 build host with the prerequisites in
[the build workflow](../.github/workflows/openwrt-current.yml). From a clean checkout:

```sh
sh scripts/build-openwrt.sh x86/64
sh scripts/build-openwrt.sh mediatek/filogic
```

Each command requires a fresh work directory under `vendor/.cache/`. Override it
with `FLINT2_OPENWRT_WORK` for an independent build. The script downloads an
official snapshot SDK, verifies its SHA-256 before extraction, pins the snapshot's
feed revisions and compiles all three packages using the selected toolchain.
No downloaded SDK or precompiled capture binary is used by the package recipes.

The backend source archive is pinned by full commit and SHA-256 in its recipe.
The capture recipe pins the upstream release archive and uses OpenWrt's libpcap
instead of privately compiling it. The capture binary reports its own minimum
aligned record size using `--flint2-buffer-size`; the service uses that value.

The host preparation helper addresses two observed snapshot SDK issues: absolute
libtool paths referring to the SDK builder, and an always-true conditional
dependency emitted by the metadata generator that Kconfig reports as a cycle.
It relocates only `.la` metadata and recognizes the exact generator text before
normalizing positive conjunctions. Checks remain enabled; unknown generator
implementations fail for review. These SDK workarounds are outside the upstream
package recipes and should be rechecked against future SDK releases.

**Actions → Build current OpenWrt packages** produces separate artifacts for x86-64
and MediaTek/Filogic. Current development OpenWrt uses **APK**, so these are `.apk`
packages rather than vendor-firmware `.ipk` files. Artifacts include the public
verification key, portable `SHA256SUMS`, source recipes/patches, SDK hash, feed
revisions, configuration log and project commit. The generated private signing
key is never uploaded. This development key is separate from the community
opkg feed's signing key.

CI also builds a packaging-only backend revision under `qualification-only/` to
test upgrade/configuration preservation. It uses the same runtime source with
only `PKG_RELEASE` changed to 2; it is not a published candidate or feed update.

## Candidate installation

Use a disposable current OpenWrt test system matching the artifact's target.
Verify the workflow/commit, SDK provenance and checksums before trusting its
generated public key. Review the key and copy only `public-key.pem` into a uniquely
named file under `/etc/apk/keys/`; do not replace OpenWrt's existing keys.
Install the three local APK files together with `apk add ./<filename>.apk ...`.
There is no need to disable signature verification. These packages are not yet
available from the default repositories.

The public configuration starts disabled with placeholder endpoints and system CA
trust. Configure the destination, format and interfaces before enabling it:

```sh
flint2-agent --check-config
/etc/init.d/flint2 restart
```

Use [the configuration guide](CONFIGURATION.md) for HTTPS/CA/header controls and
[backend support](BACKENDS.md) for OTLP, ECS NDJSON and GELF. Installing the UI is
optional. Do not install these APKs on vendor 21.02, or install the combined legacy
IPK over the split packages. Firmware/ABI migration needs its own qualification.

## Firewall behavior and scope

The common helper selects fw4 when available; the vendor fw3 path remains.
With fw4 it snapshots the current ruleset as JSON and installs/removes its own
chains and jumps in one atomic transaction. Restart and firewall reload are
idempotent. Cleanup does not require a working WAN status probe.

Forward observations cover new IPv4 DNAT attempts on the selected WAN and new
IPv4 attempts on selected VPN interfaces. Denial observations mirror the actual
matches in `drop_from_wan` and `reject_from_wan`, replacing their terminal action
with rate-limited logging in a separate chain. Existing rules and counters are
not replaced. Empty/inactive WAN deny chains produce no denial observations.
The ordinary fw4 reject handler is validated before labelling an event rejected.
Unsupported custom/stateful deny-chain expressions fail before a transaction is
applied; they are not guessed. The integration currently assumes the firewall's
WAN zone is named `wan`.

The hooks never accept, reject or drop traffic. They do not capture every possible
custom firewall denial, IPv6 flows, WireGuard handshakes or successful VPN logins.
Hardware-offloaded traffic may bypass packet capture; observed flows are not
lossless accounting. See [validation evidence](../VALIDATION.md) and
[submission readiness](OPENWRT-SUBMISSION.md) for tested environments and limits.

`tests/firewall-fw4.sh` reloads and edits its test firewall; run it only on a
disposable system. The transport integration tests use isolated configuration
and fake HTTP responses, so they do not certify a particular production receiver.
