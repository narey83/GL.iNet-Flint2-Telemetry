# Roadmap

## Delivered through 0.3.1-6

- ECS event contract with OTLP logs, ECS NDJSON and optional GELF transport.
- Native OTLP metrics and independent metric point copies in log output.
- IPv4 flow metadata, router logs, system/interface samples and device inventory.
- LuCI export controls, CA paths and interface selection with retained settings.
- Direct HTTPS destinations; native Graylog TLS setup with optional proxy examples.
- Portable Graylog content pack: ten dashboards and 183 widgets, with a setup guide
  and explicit GeoIP/ASN/intelligence enrichment requirements.
- GitHub native ARM64 builds, generic disabled IPKs, checksums, matching source
  bundles and draft releases from tags. Public releases include qualification notes.
- ARM64 capture timestamp/flag fixes with bounded live regression checks.

## Planned work

- Release qualification: measure router overhead and hardware-offload visibility,
  review dependency advisories and expand the tested firmware/version matrix.
  Existing live checks do not establish lossless accounting or a throughput benchmark.
- Portability: fw4/nftables support, IPv6 flow capture, other firmware/CPU ABIs and
  additional clean-install backend examples. Keep backend-specific projections
  outside the agent's canonical contract.
- Operations: package feed, optional bounded persistent buffering and managed
  certificate renewal. Firmware upgrades can require reinstalling the IPK.
- Additional observations: Wi-Fi station health, VPN state and DNS summaries using
  appropriate standard fields. WireGuard handshake/connection events are not yet
  collected. Inventory and forwarded attempts must not imply presence, policy
  acceptance or successful authentication.
