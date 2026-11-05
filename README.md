# GL.iNet Flint2 Telemetry

An OpenWrt telemetry agent for GL.iNet Flint 2 (GL-MT6000). Collects router health,
interface counters, WAN changes, device inventory, router logs and IPv4 flow
observations. Installs as one UCI-configured, procd-supervised `.ipk`.

The public package starts **disabled**, with placeholder endpoints and system CA
trust. No site addresses, credentials or private trust certificates are bundled.

## Standards and destinations

| Signal | Public data contract | Export |
| --- | --- | --- |
| Logs and flow observations | ECS 8.17 fields with documented `flint2.*` extensions | OTLP/HTTP JSON logs, ECS NDJSON over HTTPS, or GELF HTTP |
| Native metrics | OpenTelemetry system semantic conventions 1.45.0 where applicable; `flint2.*` for router-specific measurements | OTLP/HTTP JSON metrics |
| Optional metric event copies | Names, values, units, attributes, temporality and counter starts under `flint2.*` | Same log output |

OTLP is the default. A compatible OpenTelemetry Collector can route it to other
backends; destinations without OTLP need a supported Collector exporter or adapter.
Choose a destination that accepts the selected format. GELF is an optional log
transport; the canonical event schema stays ECS. Native metrics need a separate
metrics-capable endpoint. No traces are produced. The documented ECS subset and
transport support do not imply compatibility with every logging platform.

See [the event contract](docs/SCHEMA.md), [configuration](docs/CONFIGURATION.md) and
[backend adapters](docs/BACKENDS.md). ECS and OTel semantic conventions are separate
standards: ECS describes the event body; OTLP carries that body and typed attributes.

## Graylog setup and dashboard imports

The optional [Graylog setup guide](docs/integrations/GRAYLOG.md) covers a dedicated
GELF input, HTTPS, router configuration and native content-pack installation.
[Download 10 dashboards with 183 widgets](integrations/graylog/) adapted from a
working installation. The [catalogue](docs/integrations/GRAYLOG-DASHBOARDS.md)
explains optional GeoIP/ASN/intelligence enrichments and the portable field mapping.
The agent remains usable with other compatible logging and monitoring platforms.

## Download an IPK

Get the generic IPK and `SHA256SUMS` from
[GitHub Releases](https://github.com/narey83/GL.iNet-Flint2-Telemetry/releases/latest).
Download the matching `aarch64_cortex-a53` package only if your firmware matches
the ABI described below. Keep the corresponding source archive with redistributed
binaries. Public packages start disabled and require your own destination settings.

GitHub can also build it: **Actions → Build OpenWrt IPK → Run workflow** produces
a downloadable artifact containing the IPK, matching sources, checksums, build
metadata and Graylog imports. Manual artifacts expire after 30 days. Version tags
create a **draft** release for qualification; see [release builds](docs/RELEASES.md).

## Build

The current native capture asset targets `aarch64_cortex-a53`, OpenWrt 21.02 musl.
Only the GL-MT6000 vendor firmware with fw3/iptables has been exercised. Other
firmware ABIs, fw4/nftables and other CPU architectures are not qualified.

On a Linux x86_64 host with Python 3, curl, make, patch, autoconf, automake, libtool, bison, flex,
a C/C++ build toolchain, tar, xz and sha256sum:

```sh
./scripts/build-capture.sh
python3 scripts/build-ipk.py
```

The capture build verifies source checksums, statically links libpcap/libcdada and
uses the pinned OpenWrt SDK. It requires outbound HTTPS and several GB of free
space. Download cache/build trees are ignored under `vendor/.cache/`. A repeat
build requires removing its `work/` subdirectory. The script does not install host
packages. The `.ipk` builder is deterministic for identical inputs; identical
native binaries across different hosts are not promised.

The result is `dist/flint2-telemetry_0.3.1-5_aarch64_cortex-a53.ipk` plus SHA-256.
Run `python3 scripts/bundle-sources.py` after validation to produce its matching
source archive, including the checksum-verified upstream source tarballs.
Lua modules are MIT licensed. The bundled pmacct capture component and libraries
retain their upstream licenses; see [third-party provenance](vendor/README.md).
When distributing a binary release, include the matching source/provenance bundle
and comply with the bundled GPL notices. Do not publish only the `.ipk`.

## Install and configure

```sh
opkg install ./flint2-telemetry_0.3.1-5_aarch64_cortex-a53.ipk
uci set flint2.main.endpoint='https://collector.example.invalid/v1/logs'
uci set flint2.main.metrics_endpoint='https://collector.example.invalid/v1/metrics'
# Replace both example URLs with real HTTPS destinations before enabling.
uci set flint2.main.enabled='1'
uci commit flint2
/etc/init.d/flint2 restart
```

Install the appropriate CA file for a private PKI and set `ca_file` and, if needed,
`metrics_ca_file`. TLS verification is mandatory. Bearer/HEC-style authentication
can be supplied through an owner-only header file; see configuration examples.
Check configuration with `lua /usr/sbin/flint2-agent --check-config`.
`--once` prints collected log records without sending; `--metrics-once` prints
native metrics without sending. Those outputs can contain sensitive inventory.

Dependencies are listed in [package/Makefile](package/Makefile). Collection runs as
root to access router state and packet capture. Endpoints receive IP/MAC addresses,
device names, raw router logs and network metadata. Traffic payloads are not
exported; capture uses a 128-byte snap length for flow metadata. Keep ingestion
endpoints authenticated or network-restricted and apply an appropriate retention
policy. Header files are not package payloads and are not automatically preserved
across firmware upgrades; manage their backup separately.

## Router web settings

When LuCI is installed, open **Services → Flint2 Telemetry**. The page explains
collection capabilities, standards/destinations and limitations, shows the current
log destination, and lets you select statistics, WAN, local flow and VPN event
devices. Existing devices are listed; custom names retain devices that are currently
absent. Save & Apply reloads telemetry using the normal OpenWrt configuration path.
The page can write only the Flint2 UCI configuration, not network/firewall settings.
LuCI is optional: the agent remains usable through UCI on headless OpenWrt systems.

Clearing local flow devices means WAN-only capture; clearing VPN devices disables
VPN forwarding observations. Missing lists are not silently repopulated. The WAN
device is skipped in the local capture list to avoid capturing it twice. Network
reload triggers include custom configured logical interfaces. No VPN server is
started by selecting its device. **WireGuard handshakes/tunnel connection events
are not currently collected**; VPN events describe forwarded attempts.

## Collection and delivery limits

System samples run every 30 seconds, device inventory every five minutes and log
polling every five seconds. Inventory labels are discovered from UCI/ubus, DHCP,
static leases and optional GL.iNet client data. A lease is not proof of presence.
CPU/rate measurements need two samples and skip invalid counter deltas. Do not add
bridge and physical interface counters together.

Bundled pmacct observes each selected interface and emits IPv4 unidirectional flow
records over **loopback only**. The agent decodes them to ECS and sends HTTPS.
Max flow lifetime is 60 seconds with periodic expiry checks. LAN and WAN observations
can describe the same traffic; select `flint2.capture.scope` before aggregation.
NAT changes addresses between observation points. IPv6 flows, payload inspection,
application identification and lossless packet accounting are not implemented.
Hardware acceleration and packet drops may reduce visibility; accuracy and router
throughput impact have not been benchmarked against an external reference.

Optional package-owned firewall chains only LOG rate-limited observations; they
never accept, reject or drop traffic. They observe WAN drops and selected forwarded
connection attempts. A `forward` event is not proof that the firewall accepted the
connection. Existing forwarding/syslog/NetFlow configurations are not restored.
Disable `firewall_events` on unsupported layouts; the helper fails explicitly when
its required fw3 chain is absent. VPN interfaces must be configured for the site.

Log queues are bounded in RAM (default 2048 records); requests contain at most 64
records and 240 KiB. Native metrics use a separate queue (default eight batches).
Overflow drops oldest data and increments loss counters. Restarts lose queued data.
Transport failures and transient OTLP responses retry with the sampling interval;
OTLP partial success discards only reported rejections, while permanent OTLP errors
discard the batch. GELF/NDJSON acknowledgements use their respective HTTP success
codes. A lost acknowledgement can cause duplicates; `event.id` identifies records
within an agent run. No exactly-once or durable delivery guarantee is made.

## Firmware upgrades

The package owns its service, helper scripts and one firewall include; removing it
removes its own hooks. UCI configuration is declared a conffile. An explicitly
bundled private-site **public CA certificate** is also preserved as a conffile.
Firmware flashing may remove the agent and dependencies even when settings survive.
Reinstall a compatible package or include it in a firmware image. Factory resets
require reprovisioning. Do not reuse native binaries across incompatible ABIs.

## Development

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m py_compile scripts/*.py tests/test_*.py
LUA_PATH='./package/files/usr/lib/lua/?.lua;;' lua tests/core.lua
LUA_PATH='./package/files/usr/lib/lua/?.lua;;' lua tests/metrics.lua
LUA_PATH='./package/files/usr/lib/lua/?.lua;;' lua tests/sources.lua
LUA_PATH='./package/files/usr/lib/lua/?.lua;;' lua tests/standards.lua
```

Lua tests need Lua 5.1 and cjson. Delivery integration tests additionally require an
OpenWrt test environment; they use isolated UCI/runtime directories and a fake curl.
See [validation evidence](VALIDATION.md) for what was actually exercised.
CI checks source/package fixtures; it does not certify live router behavior.
With the agent running and WAN capture configured, `lua tests/capture-live.lua`
checks actual TCP flag preservation using an isolated loopback handshake/receiver.
`lua tests/capture-timestamps.lua` checks recent flow timestamps with 128 bounded
loopback flows. `lua tests/capture-wan.lua` observes a separate WAN probe for 60
seconds, checking rejected batches and stale timestamps; it needs real WAN traffic.
These probes export only to separate loopback receivers, not the configured SIEM.
Site configuration, local test results, dashboard IDs, certificates, build caches
and binaries remain ignored. Project source and setup help are available at
[github.com/narey83/GL.iNet-Flint2-Telemetry](https://github.com/narey83/GL.iNet-Flint2-Telemetry).
