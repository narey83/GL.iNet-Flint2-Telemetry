import unittest
from scripts.graylog_fields import migrate


class GraylogFieldTests(unittest.TestCase):
    def test_only_field_references_change(self):
        value = {'title': 'interface', 'query_string': 'flint2:telemetry AND event_kind:metric AND metric_name:flint2.logs.dropped',
                 'function': 'max(metric_value)', 'fields': ['timestamp', 'metric_attribute_cpu_mode', 'agent_version'],
                 'field': 'source_bytes'}
        changed = migrate(value)
        self.assertEqual(changed['title'], 'interface')
        self.assertEqual(changed['query_string'], 'flint2_component:telemetry AND flint2_event_kind:metric AND flint2_metric_name:flint2.logs.dropped')
        self.assertEqual(changed['function'], 'max(flint2_metric_value)')
        self.assertEqual(changed['fields'], ['timestamp', 'flint2_metric_attribute_cpu_mode', 'agent_version'])
        self.assertEqual(changed['field'], 'source_bytes')
        self.assertEqual(migrate(changed), changed)
