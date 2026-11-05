"""Graylog projection of the canonical ECS/custom attributes; not a wire schema."""
import re

CUSTOM = set('''event_kind event_type schema_version boot_id sequence cpu_used_percent
memory_total_bytes memory_available_bytes memory_used_percent uptime_seconds load_1 load_5 load_15
temperature_celsius conntrack_count conntrack_max queue_depth queue_dropped_total delivery_failed
metrics_queue_depth metrics_dropped_total metrics_rejected_total metrics_delivery_failed sample_seconds
interface interface_index rx_bytes tx_bytes operstate rx_bits_per_second tx_bits_per_second rx_errors tx_errors
rx_dropped tx_dropped wan_up wan_uptime_seconds wan_ipv4 wan_protocol device_ip device_mac device_name
inventory_source lease_expiry_raw device_network dhcp_lease_records inventory_limit metric_name metric_unit
metric_description metric_value metric_time_unix_nano metric_start_time_unix_nano metric_type
metric_temporality metric_monotonic source_flow_records source_invalid_datagrams source_log_records source_log_gaps'''.split())


def field(name):
    if name == 'flint2':
        return 'flint2_component'
    if name == 'agent_start_id':
        return 'agent_ephemeral_id'
    return 'flint2_' + name if name in CUSTOM or name.startswith('metric_attribute_') else name


def migrate(value, key=''):
    """Change field references, leaving titles, IDs, descriptions and literal values intact."""
    if isinstance(value, dict):
        return {k: migrate(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [migrate(v, key) for v in value]
    if not isinstance(value, str):
        return value
    if key in {'field', 'fields', 'selected_fields'}:
        return field(value)
    if key == 'query_string':
        return re.sub(r'\b([a-zA-Z_][a-zA-Z_0-9]*)(?=:)', lambda m: field(m[1]), value)
    if key == 'function':
        return re.sub(r'(?<=\()([a-zA-Z_][a-zA-Z_0-9]*)(?=\))', lambda m: field(m[1]), value)
    return value
