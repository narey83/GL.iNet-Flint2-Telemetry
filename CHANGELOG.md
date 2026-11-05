# Changes

## 0.3.1-2

- Synchronize the native capture ring on ARM64, publish complete records before
  readiness, and reject overwritten snapshots without changing packet timestamps.
- Align capture slots to eight bytes (264 bytes) while retaining TCP flag metadata.
- Add bounded live flow timestamp tests and invalid/wrapped timestamp fixtures.
- Use backend-neutral capability help and destination documentation; keep the
  optional Graylog integration in its own guide. The destination display reads
  each installation’s configuration.
- Link the package help to the public project repository.
- Include the native patch and change notice in corresponding source releases.

## 0.3.0-5

- Add the LuCI Services → Flint2 Telemetry page with interface selectors, capture
  switches, destination display and a capability/limitations guide. LuCI is optional.
- Validate list sizes/names and reject duplicates; honor empty lists, skip duplicate
  WAN capture, and follow custom configured network interfaces on reload.
- Restrict the page’s write ACL to the Flint2 UCI configuration.
- Extend the optional Graylog adapter with port-name labels for Internet-bound VPN traffic.

## 0.3.0-3

- Report the first three malformed local capture datagrams per run, including the
  rejection reason and size, while retaining the invalid-datagram health counter.
  A dashboard audit found occasional invalid flow-end timestamps; these are still
  rejected rather than inventing replacement times.

## 0.3.0-2

- Size the ARM64 capture buffer explicitly so alignment preserves TCP flag bytes.
  The 0.3.0-1 default truncated those bytes during live capture, leaving SYN/TCP
  dashboard panels empty despite otherwise valid flows.
- Add a controlled loopback capture regression test in addition to offline fixtures.

## 0.3.0 — schema 2

- Canonical ECS 8.17 event bodies and typed OTLP log attributes; ECS NDJSON output.
- Native OTel metrics retained as a separate signal, with optional log point copies.
- Public package disabled by default, generic endpoints/system CA trust, optional
  owner-only authentication header files and explicit private-site build profiles.
- Bundled IPv4 pmacct capture, router log reader and package-owned LOG-only fw3 hooks.
- Documented source-pinned native build, third-party notices and source CI checks.

Breaking export change: formerly bare custom log fields now live under `flint2.*`.
GELF flattens dots to underscores; for example `metric_value` becomes
`flint2_metric_value`, while ECS `event.kind` becomes `event_kind`. The collector
record discriminator becomes `flint2_event_kind`. Full nested JSON is retained in
GELF `ecs_document`; multi-value arrays are JSON strings in flattened GELF fields.
`--once` now emits the configured wire representation. Graylog field migrations
are adapter operations; other consumers should update their schema mappings.
