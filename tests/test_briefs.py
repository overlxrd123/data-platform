import json
import os
import unittest
os.environ.setdefault('DEEPSEEK_KEY','')
from analysis.briefs import get_brief, LOADERS


class BriefTests(unittest.TestCase):
    def test_all_business_briefs_and_routes(self):
        from fastapi.testclient import TestClient
        import app
        client=TestClient(app.app)
        for slug in LOADERS:
            brief=get_brief(slug)
            self.assertTrue(all(brief[k] for k in ['question','evidence','interpretation','action','verification','status']))
            self.assertEqual(client.get('/api/brief/'+slug).json(),brief)
            self.assertIn('/static/brief.js',client.get('/module/'+slug).text)
            json.dumps(brief,allow_nan=False)
        self.assertEqual(client.get('/api/brief/loan').status_code,404)

    def test_cross_groups_cover_survey_and_holdout(self):
        survey=get_brief('survey')['detail']['rows']
        self.assertEqual(sum(int(row[1]) for row in survey),1453)
        from analysis.portfolio import get_housing_analysis
        house=get_brief('housing')['detail']['rows']
        self.assertEqual(sum(int(row[1]) for row in house),get_housing_analysis()['metrics']['validation_count'])
        self.assertTrue(all(row[2].startswith('$') for row in house))

    def test_movie_concentration_reconciles_to_full_sample(self):
        from analysis.portfolio import get_movies_analysis
        rows=get_movies_analysis()['movies']
        expected=100*sum(r['revenue_yi'] for r in rows[:10])/sum(r['revenue_yi'] for r in rows)
        self.assertEqual(get_brief('movies')['detail']['rows'][0][1],f'{expected:.1f}%')


if __name__=='__main__':unittest.main()
