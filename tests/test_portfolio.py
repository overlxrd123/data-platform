"""对原始样本对账、验证集边界，以及旧模块退出后的路由和问答回归。"""
import json
import os
import unittest
import numpy as np
import pandas as pd
from unittest.mock import patch
from analysis.portfolio import DATA, get_housing_analysis, get_movies_analysis, get_survey_analysis

os.environ.setdefault('DEEPSEEK_KEY', '')


class PortfolioTests(unittest.TestCase):
    def test_movies_multilabel_and_totals(self):
        d = get_movies_analysis()
        raw = pd.read_excel(DATA / 'movies.xlsx')
        self.assertEqual(len(d['movies']), len(raw))
        self.assertAlmostEqual(sum(r['revenue_yi'] for r in d['movies']), raw['累计票房'].sum()/1e8)
        expected = raw['作品类型'].str.split(',').explode().str.strip().value_counts().to_dict()
        self.assertEqual({r['tag']: r['count'] for r in d['genres']}, expected)
        self.assertGreater(sum(expected.values()), len(raw))
        self.assertTrue(all(r['snapshot'] for r in d['movies']))
        json.dumps(d, allow_nan=False)

    def test_survey_endpoints_and_denominators(self):
        d = get_survey_analysis()
        raw = pd.read_csv(DATA / 'mcdonalds.csv')
        self.assertEqual(sum(r['count'] for r in d['segments']), len(raw))
        self.assertEqual(sum(r['count'] for r in d['visits']), len(raw))
        self.assertEqual(sum(r['count'] for r in d['ages']), len(raw))
        self.assertEqual(d['overview']['missing_like'], 0)
        self.assertAlmostEqual(d['overview']['mean_like'], raw['Like'].str.extract(r'([+-]?\d+)$')[0].astype(int).mean())
        for r in d['attributes']:
            self.assertAlmostEqual(r['yes_pct'], 100*r['yes']/r['valid'])
        json.dumps(d, allow_nan=False)

    def test_housing_holdout_independent_of_kaggle_unlabeled(self):
        d = get_housing_analysis()
        raw = pd.read_csv(DATA / 'housing' / 'train.csv')
        m=d['metrics']
        self.assertEqual(m['train_count']+m['validation_count'],len(raw))
        self.assertEqual(len(d['scatter']), len(raw))
        self.assertEqual(len(d['validation']),m['validation_count'])
        actual=raw.set_index('Id')['SalePrice']
        self.assertTrue(all(r['actual']==actual[r['id']] for r in d['validation']))
        self.assertAlmostEqual(m['mae_usd'], np.mean([abs(r['actual']-r['predicted']) for r in d['validation']]))
        self.assertEqual(d['overview']['unlabeled_records'],1459)
        self.assertNotIn('SalePrice',pd.read_csv(DATA/'housing'/'test.csv').columns)
        json.dumps(d, allow_nan=False)

    def test_migration_routes_and_agent(self):
        import app
        from fastapi.testclient import TestClient
        client=TestClient(app.app)
        active=set(client.get('/health').json()['modules'])
        self.assertEqual(active,{'food','survey','housing','movies','rental','jobs','retailrocket'})
        for old,new in [('game','survey'),('loan','movies'),('retention','retailrocket')]:
            response=client.get('/module/'+old,follow_redirects=False)
            self.assertEqual(response.status_code,307)
            self.assertEqual(response.headers['location'],'/module/'+new)
            self.assertEqual(client.get('/api/'+old).status_code,410)
        for slug in ['housing','movies','survey']:
            self.assertIn('portfolio.js',client.get('/module/'+slug).text)
            self.assertEqual(client.get('/api/'+slug).status_code,200)
        for page in ['/', '/workspace', '/agent']:
            html=client.get(page).text
            self.assertNotIn('/module/loan',html)
            self.assertNotIn('/module/game',html)
            self.assertNotIn('/module/retention',html)
        with patch.object(app,'DEEPSEEK_KEY',''):
            for question,module in [('美国房价预测误差多少','housing'),('电影评分与票房有什么关系','movies'),('麦当劳品牌认知','survey'),('D7留存回访率多少','retailrocket')]:
                answer=app._fallback_agent(question,[])
                self.assertTrue(answer['tools'][0].startswith(module+'.'))
                self.assertTrue(answer['reply'])
        # No old model or simulated dataset is part of the active AI tool directory.
        from agent_runtime import FOCUSES
        self.assertEqual(set(FOCUSES),active)


if __name__=='__main__':
    unittest.main()
