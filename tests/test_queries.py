import asyncio
import json
import unittest
from unittest.mock import patch
import httpx
from analysis.queries import query,validate_params
from agent_runtime import Agent


def response(value):
    return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(value)}}]})


class QueryTests(unittest.TestCase):
    def test_seven_modules_have_bounded_json_results(self):
        for module in ['movies','food','rental','housing','jobs','survey','retailrocket']:
            r=query(module,{'limit':3})
            self.assertGreater(r['total_matches'],0)
            self.assertEqual(len(r['rows']),3)
            json.dumps(r,allow_nan=False)

    def test_filters_sorting_and_disjoint_pages(self):
        first=query('movies',{'genre':'动画','limit':3,'sort_by':'douban'})
        second=query('movies',{'genre':'动画','limit':3,'offset':3,'sort_by':'douban'})
        self.assertEqual(first['total_matches'],11)
        self.assertTrue(all('动画' in r['genre'] for r in first['rows']))
        self.assertTrue(set(r['name'] for r in first['rows']).isdisjoint(r['name'] for r in second['rows']))
        self.assertEqual([r['douban'] for r in first['rows']],sorted([r['douban'] for r in first['rows']],reverse=True))
        for module,params in [('food',{'district':'海淀','max_price':100}),('rental',{'rent_type':'整租','max_price':3000}),('housing',{'max_price':150000}),('jobs',{'city':'北京','min_price':15000})]:
            for row in query(module,params)['rows']:
                if 'max_price' in params:self.assertLessEqual(row['price'],params['max_price'])
                if 'min_price' in params:self.assertGreaterEqual(row['price'],params['min_price'])
        self.assertEqual(query('rental',{'max_price':1})['total_matches'],0)

    def test_date_filters_and_unsafe_params(self):
        r=query('retailrocket',{'start_date':'2015-07-01','end_date':'2015-07-03'})
        self.assertEqual(r['total_matches'],3)
        for p in [{'limit':200},{'offset':-1},{'sql':'DROP TABLE x'},{'min_price':100,'max_price':1},{'order':'anything'},{'max_price':float('inf')}]:
            with self.assertRaises(ValueError):validate_params('movies',p)

    def test_question_fallback_and_followup_filters(self):
        import app
        history=[{'role':'user','content':'列出前3部动画电影'}]
        with patch.object(app,'DEEPSEEK_KEY',''):
            listed=app._fallback_agent('电影有些什么电影',[])
            self.assertEqual(listed['tools'],['movies.query'])
            self.assertIn('名称：',listed['reply'])
            next_page=app._fallback_agent('下一页',history)
            self.assertIn('第4条',next_page['reply'])
            self.assertIn('共11条',next_page['reply'])
            food=app._fallback_agent('去北京吃顿饭预算100以内，我可以吃什么',[])
            self.assertEqual(food['tools'],['food.query'])
            self.assertIn('名称：',food['reply'])


class PlanCorrectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_json_corrected_once_then_query(self):
        calls=[];tools=[]
        def handler(req):
            calls.append(json.loads(req.content))
            if len(calls)==1:return response([])
            if len(calls)==2:return response({'action':'call','calls':[{'module':'movies','focus':'query','params':{'limit':3}}]})
            return httpx.Response(200,content=b'data: {"choices":[{"delta":{"content":"listed"}}]}\n\ndata: [DONE]\n\n')
        def tool(*args):tools.append(args);return '{"rows":[{"name":"example"}]}'
        agent=Agent('fake-key','JSON',{'movies':'电影'},tool,lambda *a:{'reply':'fallback','tools':[]},lambda f:f,transport=httpx.MockTransport(handler))
        events=[e async for e in agent.events({'message':'有哪些电影'})]
        self.assertEqual(events[-1]['source'],'llm')
        self.assertEqual(len(calls),3) # original plan, one correction, answer
        self.assertEqual(len(tools),1)

    async def test_bad_plan_twice_falls_back_without_tools(self):
        requests=[]
        def handler(req):requests.append(req);return response({'action':'call','calls':[{'module':'movies','focus':'query','params':{'limit':1000}}]})
        def tool(*a):self.fail('invalid plan executed a tool')
        agent=Agent('fake-key','JSON',{'movies':'电影'},tool,lambda *a:{'reply':'名单兜底','tools':['movies.query']},lambda f:f,transport=httpx.MockTransport(handler))
        events=[e async for e in agent.events({'message':'有哪些电影'})]
        self.assertEqual(len(requests),2)
        self.assertEqual(events[-1]['fallback_reason'],'invalid_params')
        self.assertEqual(events[-1]['reply'],'名单兜底')

    async def test_all_calls_validated_before_any_execution(self):
        requests=[]
        def handler(req):
            requests.append(req)
            return response({'action':'call','calls':[{'module':'movies','focus':'query'},{'module':'movies','focus':'unsupported'}]})
        def tool(*a):self.fail('partial invalid plan executed a tool')
        agent=Agent('fake-key','JSON',{'movies':'电影'},tool,lambda *a:{'reply':'fallback','tools':[]},lambda f:f,transport=httpx.MockTransport(handler))
        result=[e async for e in agent.events({'message':'有哪些电影'})]
        self.assertEqual(len(requests),2)
        self.assertEqual(result[-1]['fallback_reason'],'invalid_focus')


if __name__=='__main__':unittest.main()
