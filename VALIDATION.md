# Validation evidence — 2026-11-05

## 0.3.0 / schema 2

Target: GL.iNet GL-MT6000, vendor OpenWrt 21.02-SNAPSHOT, kernel 5.4.238,
Lua 5.1.5, aarch64_cortex-a53 musl. Graylog 4.3.15.

Completed:

- Nine Python tests passed: deterministic package fixtures, architecture rejection,
  explicit site profiles, public defaults, source allowlist/checksum rejection,
  dashboard preservation/layout, field migration and clean-install index-set selection.
- On-router Lua tests passed: 31 core, 53 metrics, 25 source decoder checks, plus
  ECS/OTLP/GELF contract checks covering typed arrays/booleans/integers, standard
  field names, unidirectional byte semantics and lossless nested GELF JSON recovery.
- All three isolated delivery integrations passed: transport/redirect retention,
  independent native metrics queue, retry/partial acceptance/permanent rejection,
  and permanent OTLP log rejection without queue poisoning. Secret header files
  with group/other access were rejected; owner-only files were accepted.
- Official OpenTelemetry Protobuf definitions accepted the new structured ECS log
  payload. The unchanged native metric encoder's prior real-Collector test is below.
- Clean Linux x86_64 build from checksum-pinned SDK, pmacct 1.7.9 and libpcap 1.11.0
  succeeded. The resulting ARM64 binary ran on the router. The build emitted
  upstream compiler warnings (including sys/poll.h forwarding and ar flags), not
  build errors. This is build-script verification, not proof of bit-identical native
  output on different hosts.
- Public and explicit private-site packages built successfully. The site package
  was installed; procd supervised the agent and four capture instances. Capture
  receivers bind loopback only. Package-owned fw3 chains contain LOG rules only.
- Graylog simulator exercised log and LAN/WAN flow routing/enrichment without
  processing errors. Actual ingestion then confirmed WAN flows, named LAN flows,
  drop geolocation, forwarded-attempt service labels and metric event copies.
- All 183 widget queries across ten dashboards executed without query/search-type
  errors after live flow ingestion populated the index. Before ingestion, one
  existing flow-bytes sort failed on an empty index; its later execution passed.
  The Flint2 overview rendered live CPU, memory and temperature values in-browser.
  Inactive VPN/threat scenarios may correctly have no observations.
- At the final sampled health check, the agent reported zero queue drops, invalid
  datagrams, log gaps and delivery failure, with an empty queue. This is a bounded
  observation, not a guarantee of loss-free telemetry. No processing errors were
  found in the checked recent version-0.3 messages.
- Legacy remote syslog and all softflowd profiles remained disabled. No standalone
  softflowd exporter was installed or re-enabled. The old device timer stays off.
- ShellCheck (BusyBox scripts and POSIX build script), Python compilation and Lua
  compiler loading passed. Public source/package material was checked separately
  from ignored private site configuration and binaries.

Limits:

- `luac`, `luacheck`, `stylua` and `ruff` were unavailable. Lua syntax was checked
  with the interpreter's `loadfile`; dedicated Lua/Python formatter checks were
  not performed. No Git diff was available because this workspace is not a Git
  repository; the public source allowlist and changed files were reviewed directly.
- Capture statistics during initial operation reported packet drops under load.
  Flow counts/bytes are observations, not complete accounting. Neither throughput
  accuracy nor hardware-offload visibility/CPU cost has been benchmarked.
- fw4/nftables, IPv6 flows, other firmware ABIs and direct Splunk HEC were not tested
  or implemented. No exhaustive security audit or comprehensive CVE scan was run.
  [pmacct's published advisories](https://github.com/pmacct/pmacct/security/advisories)
  and the [libpcap 1.11.0 changelog](https://github.com/the-tcpdump-group/libpcap/blob/libpcap-1.11.0/CHANGES)
  were reviewed; that does not establish absence of vulnerabilities.
- GitHub CI configuration is supplied; no hosted Actions run or GitHub publication
  occurred. Release qualification and matching-source distribution remain explicit.

## Prior 0.2 native metric interoperability evidence

A temporary OpenTelemetry Collector Contrib 0.164.0 accepted 21 metric families and
85 points, including per-core CPU and cumulative network starts. Prometheus export
contained 12 network byte series, 28 CPU mode series and two memory-state series.
Official Protobuf definitions accepted the metric JSON. The validation container
was stopped/removed. No permanent Collector was deployed; live native OTLP metrics
export remains disabled, while Graylog receives structured point copies.

## Follow-up dashboard audit and simulation

All 183 widgets were checked for actual matching documents and aggregation values,
in addition to query errors, in both their configured windows and a forced recent
15-minute window. This found zero TCP flags in live flows despite successful queries.
A controlled test reproduced the loss; offline pcap replay preserved the same flags.
The ARM64 default plugin buffer rounded 259 bytes down to 256, truncating the three
extra bytes. Explicit `plugin_buffer_size: 260` preserves a complete record. A live
loopback TCP/SYN regression test now passes using the installed capture settings.

Fourteen non-indexing Graylog pipeline scenarios passed: SYN, SYN/ACK, ACK, RST,
FIN, guest-device enrichment, VPN/internal labels, unknown services, P2P drops,
failed SSH/UPnP logs, outbound SYN and inbound/outbound Tor-labelled SYN. A separate
Tor-source simulation confirmed the real Tor lookup marks its source. Addresses
were selected from [Tor's official exit list](https://check.torproject.org/torbulkexitlist), not from fabricated intelligence flags.
The optional native exporter-health families were generated in the isolated
fake-HTTP integration; production native export remains disabled. No synthetic
flow/authentication/threat events were indexed for these pipeline tests.

Nine Python checks, ShellCheck and Python compilation passed after the buffer fix.
The agent's capture rejection diagnostics are now rate-limited to the first three
rejections per run. Stored indexer failures were historical: three from 19:47–20:07
UTC on this date, before the current schema/export correction. They were retained.

The final check found a remaining capture-quality issue: occasional batches have
invalid end times (for example, last-uptime 1,382,455,523 ms while exporter uptime
was 6,807 ms). The decoder correctly rejects them; their origin was not resolved in that release; see the 0.3.1 evidence below.
One isolated 15-second WAN capture accepted 1,189 flow records and rejected one
datagram for this reason. This is not an accuracy benchmark or a fixed rejection
rate. Production counters and rate-limited diagnostics make the rejection visible.
No replacement timestamps are fabricated. Live queue drops and delivery failure
were zero at the checked sample, which does not include capture-side rejection.

## LuCI interface controls and capability guide — 0.3.0-5

The Services → Flint2 Telemetry page was installed and exercised in the signed-in
router UI. Its selectors enumerate real devices and retain absent custom devices.
Adding lan1 to statistics through the UI, then Save & Apply, changed the agent PID
and produced new lan1 interface records in Graylog. The test selection was removed
through the same UI, and a semantic comparison verified that all original UCI
settings (including destinations and aliases) were preserved. List order was
normalized by LuCI. The final page and expandable capability/limitations guide
rendered successfully; a private screenshot is saved under local/.

Node tests cover the actual view validators, list limits, invalid names, duplicate
entries, optional empty lists, status, destination display, help content and the
restricted write ACL. Node syntax checking, nine Python checks, ShellCheck and
Python compilation passed. On-router tests passed: 43 core checks, 53 metrics,
25 source checks and the standards contract suite. Missing lists now stay empty;
local WAN duplication is skipped and configured logical networks receive reload
triggers. LuCI is optional and no additional agent runtime dependency was added.

The concurrent VPN issue was a stopped WireGuard server: the GL.iNet panel
confirmed OFF, with no tunnel device/listener. The user clarified that the client
was sending without receiving, then explicitly authorized starting the existing
server. After starting it through GL.iNet's panel, the router showed wgserver,
UDP 51820 listeners and a successful recent peer handshake; the panel showed one
online client and bidirectional byte counts. Graylog received real VPN forwarding
observations with the expected peer label. Twelve of thirteen VPN widgets had
matching data (the unknown-peer filter had none); all thirteen queries passed.
Existing keys and profiles were retained. Current telemetry observes forwarding,
not handshake events; the handshake was independently verified from WireGuard.

The optional Graylog compatibility adapter now labels Internet-bound VPN service
ports using the port-name lookup. Existing LAN-specific service labels remain in
the legacy pipeline. Five simulator cases passed: Internet DNS, Internet HTTPS,
LAN HTTPS, an unrelated zone and a dropped packet. These are port labels, not
observed application identities. Live records created before this rule were not
rewritten, and no newly labelled live record had arrived at the final check.
Ten Python tests passed after adding the rule-scope regression test.


## ARM64 flow timestamp repair — 0.3.1-1

Instrumentation found valid libpcap timestamps but partly zeroed timestamps at the
nfprobe shared-memory consumer. The writer published a plain sequence before the
record count, while the reader copied without acquire ordering or overwrite
validation. The corresponding-source patch now publishes complete slots with
release ordering, reads with acquire ordering and rechecks the copied sequence.
Capture slots are 264 bytes to retain TCP extras and eight-byte alignment.
Timestamp validation remains strict; no dates are replaced or clamped.

A simultaneous 60-second WAN comparison used separate loopback receivers and the
same 264-byte slot size. The original executable accepted 3,883 records but emitted
five rejected datagrams and ten invalid/stale record times. The patched executable
accepted 3,941 records with zero rejected datagrams and zero invalid/stale times.
Raw uptime ages were checked for every record, including records the decoder
would otherwise accept. This is a bounded observation, not a loss-rate benchmark
or a guarantee that every capture failure is eliminated.

A bounded loopback regression passed with 128 flows and 20,480 packets, zero
rejected datagrams and zero stale timestamps. An initial attempt overlapped the
WAN receiver port and failed to bind; rerunning after the WAN probes ended passed.
The installed package also passed the TCP/SYN flag handshake regression. The
upgrade preserved the live UCI configuration byte-for-byte and WireGuard remained
running. LuCI now labels its dynamic, per-installation display “Configured log
destination”; the public package stays disabled with generic placeholder URLs.

Ten Python tests, Node LuCI checks, Python compilation, ShellCheck (BusyBox dialect
for OpenWrt scripts), 43 core / 53 metrics / 29 source Lua checks and the ECS/OTLP/
GELF contract checks passed. The native patch compiled with the pinned SDK;
readelf showed the existing libc/libgcc/libstdc++ dependencies, no libatomic, and
BIND_NOW. No dedicated C static analyzer was run. ShellCheck with generic POSIX sh
warned about existing BusyBox-supported local variables; the appropriate BusyBox
check passed without suppressions.


The installed capture executable then passed a 120-second real-WAN quality check:
8,759 valid records, 691,921 observed packets, zero rejected datagrams and zero
invalid/stale record times. Before the help-page-only package revision, production
health at 22:21:15 UTC reported 8,638 flow records, zero invalid datagrams, zero log
gaps, an empty delivery queue, zero queue drops and zero delivery failures.
The isolated HTTP integration suite also passed GELF retries/redirect rejection,
native metric partial-success/permanent rejection handling, OTLP log 503 recovery,
and credential-file permission checks.

Package 0.3.1-2 adds backend-neutral help and a public repository documentation
link; its native capture executable and telemetry encoding are unchanged from
0.3.1-1. Node checks exercise the generic wording and safe external-link attributes.
The public source allowlist was inspected for site addresses and known secret
material. A private-key-marker match was a deliberate rejection-test fixture with
no key contents. Dedicated secret scanners and C/Lua static analyzers were not
available. Git whitespace checks passed outside the upstream patch, whose context
lines preserve upstream whitespace for exact application.

Package 0.3.1-3 updates the project help URL to the renamed
`narey83/GL.iNet-Flint2-Telemetry` repository. Collection and native capture
behavior are unchanged.

The initial GitHub run passed Python, Node and Lua but its older ShellCheck did
not recognize the `busybox` dialect. CI now uses the supported `dash` dialect for
the ash-compatible scripts (including local variables), without disabling any
checks. The same command passed locally.


## Portable Graylog dashboard content pack

The published revision-1 JSON contains ten dashboards, thirteen pages, 183 widgets,
one input-scoped stream, sixteen backend-only projection rules and one pipeline.
It was installed on Graylog 4.3.15 under a temporary content-pack ID with a placeholder
input ID. All 28 entities were new, not reused originals. The stream's exact input
selector prevents accidental matching while reviewing the import. It was explicitly
paused for the final checks: this server ignores the stream entity's disabled flag
on installation, which is documented in the setup guide.

All imported widget searches executed against a 60-second window of existing real
telemetry with zero query/search-type errors. Ten simulator cases passed, covering
SYN/SYN-ACK/ACK/RST/FIN masks, outbound UDP volume, port choice, byte/packet thresholds,
private/public VPN destinations and unrelated modules/datasets. Checks verified
canonical fields were not changed. Simulator messages were never sent to an input;
a subsequent index search found zero of these messages. Optional GeoIP/ASN/threat
provider data was not exported or simulated as real enrichment.

The initial attempts exposed differences between saved searches and native content-
pack entities (message-list fields and enum-valued stream-rule types). Corrected
artifacts installed successfully. The final temporary installation and uploaded
definition were removed. All original ten dashboard objects and saved searches
matched their pre-export definitions exactly, and no temporary stream remained.

Fifteen Python tests passed, including artifact checksum, all widget/search/position
references, exact input/stream scoping, original-ID/address exclusions and the rule
write namespace. The source bundler now includes the integration definitions.
Python compilation, Node LuCI checks and ShellCheck also passed. No runtime agent
or router configuration change was needed for the documentation/import addition.
Other Graylog versions and external GeoIP/intelligence providers were not tested.


## LuCI export controls and direct TLS guidance — 0.3.1-6

The LuCI page now exposes enabled, format, log endpoint/CA trust, metric log copies
and native metrics with their own endpoint and optional CA override. Node checks
exercise accepted direct GELF HTTPS host/port paths, all three format choices,
invalid/insecure/credential-bearing URLs and conditional metrics controls. The
write ACL remains limited to Flint2 configuration, with no shell execution grants.

The local profile IPK was installed on GL-MT6000. Browser checks showed the current
GELF profile, all three formats, conditional native metrics endpoint/CA fields and
an inline rejection of an HTTP URL. Save & Apply and the service configuration check
ran. The first apply exposed legacy LuCI 21.02 ignoring retain=true and removing an
inactive metrics endpoint. An explicit active-only remove handler fixes that for
metrics destinations and dependent interface lists, while preserving normal removal
of visible optional fields. Node regression checks cover both behaviors. The lost
endpoint was restored through the GUI; the final UCI comparison matched every
original value, allowing interface-list ordering differences. Native metrics remain
disabled, metric event copies enabled, and the original interface/alias profile is
preserved. WireGuard remained up.

The installed Graylog 4.3.15 GELF HTTP input type was queried read-only: it exposes
Enable TLS, TLS cert/key paths, TLS key password, client-auth mode and bulk receiving.
The guide now describes a direct TLS input and Docker TLS port/certificate setup
before the optional proxy example. No Caddy dependency exists in the agent/package.
The existing site ingestion path was not migrated to a new Graylog TLS listener;
the direct-input guide is based on the server's exposed options and official docs,
not a claim of a new end-to-end Graylog direct-TLS deployment. Client-certificate
(mTLS-required) inputs are not supported by the current exporter.
