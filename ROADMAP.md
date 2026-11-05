# Roadmap

- Current work: ECS event contract, native OTLP logs/metrics, explicit GELF adapter,
  IPv4 flow/log sources, privacy-safe package defaults and reproducible source inputs.
- Release qualification: repeat native build and delivery checks, measure router
  overhead and hardware-offload visibility, review dependency advisories, document
  supported firmware versions and supply matching GPL source with binary releases.
- Portability: fw4/nftables adapter, IPv6 flow source, clean-install backend examples
  for compatible logging and monitoring platforms. Keep backend-specific projections out of the agent.
- Operations: package feed, settings-preserving reinstall guidance, optional bounded
  persistent buffering and managed certificate renewal.
- Additional observations: Wi-Fi station health, VPN state and DNS summaries using
  appropriate standard fields. Inventory and attempted connections must not imply
  presence, policy acceptance or successful authentication.
