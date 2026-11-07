import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault('DEEPSEEK_KEY', '')
from analysis.retailrocket import get_retailrocket_analysis


class RetailrocketTests(unittest.TestCase):
    def test_snapshot_reconciliation(self):
        d = get_retailrocket_analysis()
        self.assertEqual(d['overview']['events'], 2756101)
        self.assertEqual(len(d['daily']), 137)
        self.assertEqual([int(r['pair_count']) for r in d['funnel']], [2124281, 43058, 15037])
        self.assertEqual([int(r['purchase_pairs']) for r in d['windows']], [14535, 15107, 15520])
        self.assertEqual([int(r['returned_visitors']) for r in d['retention']], [38775, 7607, 1795])
        self.assertTrue(any(r['retention_rate_pct'] is None for r in d['cohorts']))
        self.assertEqual(sum(r['cart_events'] for r in d['availability']), 69332)
        self.assertFalse(d['provenance']['is_live'])
        json.dumps(d, allow_nan=False)

    def test_routes_and_agent(self):
        import app
        from fastapi.testclient import TestClient
        client = TestClient(app.app)
        self.assertEqual(client.get('/api/retailrocket').status_code, 200)
        self.assertIn('retailrocket.js', client.get('/module/retailrocket').text)
        self.assertIn('/module/retailrocket', client.get('/workspace').text)
        with patch.object(app, 'DEEPSEEK_KEY', ''):
            answer = app._fallback_agent('电商留存和漏斗', [])
            self.assertEqual(answer['tools'], ['retailrocket.overview'])
            self.assertIn('985', answer['reply'])
        tool = json.loads(app._agent_tool('retailrocket', 'funnel'))
        self.assertIn('windows', tool)
        self.assertFalse(tool['is_live'])


if __name__ == '__main__':
    unittest.main()
