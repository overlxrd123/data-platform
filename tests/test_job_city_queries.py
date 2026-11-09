import json
import unittest
from unittest.mock import patch

import httpx
import pandas as pd

from analysis.queries import query, job_city_intent, job_city_params, infer_params
from agent_runtime import Agent


class CityAggregationTests(unittest.TestCase):
    def test_aggregate_full_filtered_sample_before_limit(self):
        rows = [{'name':'数据分析师','city':'上海','family':'数据分析','price':15000,'education':'本科'} for _ in range(12)]
        rows += [{'name':'数据分析师','city':'北京','family':'数据分析','price':30000,'education':'本科'},
                 {'name':'数据分析师','city':'深圳','family':'数据分析','price':20000,'education':'硕士'},
                 {'name':'数据开发','city':'北京','family':'数据开发','price':50000,'education':'本科'}]
        with patch('analysis.queries._table', return_value=(pd.DataFrame(rows),'price','元')):
            result=query('jobs',{'view':'cities','family':'数据分析','limit':1})
            self.assertEqual(result['matching_jobs'],14)
            self.assertEqual(result['total_matches'],3)
            self.assertEqual(result['rows'][0]['city'],'上海')
            self.assertEqual(result['rows'][0]['count'],12)
            self.assertEqual(result['rows'][0]['share_pct'],85.71)
            ranked=query('jobs',{'view':'cities','family':'数据分析','education':'本科','sort_by':'monthly_median'})
            self.assertEqual(ranked['matching_jobs'],13)
            self.assertEqual(ranked['rows'][0]['city'],'北京')
            self.assertEqual(sum(r['count'] for r in ranked['rows']),13)
            empty=query('jobs',{'view':'cities','family':'不存在'})
            self.assertEqual(empty['matching_jobs'],0)
            self.assertEqual(empty['rows'],[])

    def test_real_data_city_totals_reconcile_to_filtered_jobs(self):
        detail=query('jobs',{'family':'数据分析'})
        first=query('jobs',{'family':'数据分析','view':'cities','limit':20})
        rows=first['rows']
        if first['has_more']:
            rows+=query('jobs',{'family':'数据分析','view':'cities','limit':20,'offset':20})['rows']
        self.assertEqual(first['matching_jobs'],detail['total_matches'])
        self.assertEqual(sum(r['count'] for r in rows),detail['total_matches'])
        self.assertEqual(len(rows),first['total_matches'])
        self.assertEqual([r['count'] for r in rows],sorted((r['count'] for r in rows),reverse=True))

    def test_intent_filters_and_chinese_limit(self):
        self.assertTrue(job_city_intent('数据分析岗位在哪些城市比较多'))
        self.assertTrue(job_city_intent('按城市拆一下'))
        self.assertFalse(job_city_intent('北京有哪些数据分析岗位明细'))
        self.assertEqual(infer_params('movies','票房最高的前五部电影')['limit'],5)
        self.assertEqual(infer_params('movies','国产电影票房最高的五部电影是什么')['limit'],5)
        params=job_city_params('那本科呢',[{'role':'user','content':'数据分析岗位在哪些城市比较多'}])
        self.assertEqual(params['family'],'数据分析')
        self.assertEqual(params['education'],'本科')
        params=job_city_params('按城市拆一下',[{'role':'user','content':'本科的数据分析岗位有哪些'}])
        self.assertEqual(params['family'],'数据分析')
        self.assertEqual(params['sort_by'],'count')
        history=[{'role':'user','content':'数据分析岗位在哪些城市比较多'}]
        for offset in (8,16,24):
            page=job_city_params('下一页',history)
            self.assertEqual(page['offset'],offset)
            history.append({'role':'user','content':'下一页'})
        params=job_city_params('各城市哪些岗位比较多',[{'role':'user','content':'北京最低薪资的本科数据分析岗位明细'}])
        self.assertEqual(params['order'],'desc')
        self.assertNotIn('city',params)

    def test_fallback_and_detail_stay_distinct(self):
        import app
        with patch.object(app,'DEEPSEEK_KEY',''):
            result=app._fallback_agent('数据分析岗位在哪些城市比较多',[])
            self.assertEqual(result['tools'],['jobs.cities'])
            self.assertIn('岗位族筛选：数据分析',result['reply'])
            self.assertIn('采集样本',result['reply'])
            detail=app._fallback_agent('北京有哪些数据分析岗位明细',[])
            self.assertEqual(detail['tools'],['jobs.query'])
            followup=app._fallback_agent('那本科呢',[{'role':'user','content':'数据分析岗位在哪些城市比较多'}])
            self.assertEqual(followup['tools'],['jobs.cities'])


class CityPlanTests(unittest.IsolatedAsyncioTestCase):
    async def test_record_plan_and_unsupported_final_are_replaced_by_aggregation(self):
        import app
        cases=[({'action':'call','calls':[{'module':'jobs','focus':'query','params':{'family':'算法','limit':8}}]},'数据分析岗位在哪些城市比较多',[]),
               ({'action':'final','reply':'北京岗位最多'},'数据分析岗位在哪些城市比较多',[]),
               ({'action':'call','calls':[{'module':'jobs','focus':'query'}]},'那本科呢',[{'role':'user','content':'数据分析岗位在哪些城市比较多'}])]
        for decision,message,history in cases:
            with self.subTest(decision=decision):
                requests=[];tool_calls=[]
                def handler(req):
                    requests.append(json.loads(req.content))
                    if len(requests)==1:
                        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(decision)}}]})
                    return httpx.Response(200,content=b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n')
                def tool(module,focus,params):
                    tool_calls.append((module,focus,params))
                    return app._agent_tool(module,focus,params)
                agent=Agent('fake','JSON',{'jobs':'招聘'},tool,app._fallback_agent,lambda f:f,transport=httpx.MockTransport(handler))
                events=[event async for event in agent.events({'message':message,'history':history})]
                self.assertEqual(events[-1]['source'],'llm')
                self.assertEqual(events[-1]['tools'],['jobs.cities'])
                self.assertEqual(tool_calls[0][2]['family'],'数据分析')
                if '本科' in message:self.assertEqual(tool_calls[0][2]['education'],'本科')
                tool_results=json.loads(requests[-1]['messages'][-1]['content'].split('\n',1)[1])
                result=json.loads(tool_results[0]['result'])
                self.assertEqual(result['view'],'cities')
                self.assertGreater(result['matching_jobs'],len(result['rows']))
                self.assertIn('count',result['rows'][0])


if __name__=='__main__':unittest.main()
