import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('routing', ROOT / 'scripts/connect-existing-dashboards.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RoutingTests(unittest.TestCase):
    def test_vpn_service_projection_is_scoped_and_allows_internet_destinations(self):
        rules = module.projection_rules('dedicated-input')
        self.assertEqual(len({r['title'] for r in rules}), len(rules))
        source = next(r['source'] for r in rules if r['title'] == 'Flint2 legacy VPN service label')
        for condition in ['gl2_source_input) == "dedicated-input"', 'event_dataset) == "flint2.router_log"',
                          'observer_ingress_zone) == "vpn"', 'event_action) == "forward"',
                          'has_field("destination_port")']:
            self.assertIn(condition, source)
        self.assertNotIn('cidr_match', source, 'Internet destinations need service labels too')
        self.assertIn('lookup_value("port-name"', source)
        self.assertNotIn('network_application', source, 'A port lookup is not application identification')
