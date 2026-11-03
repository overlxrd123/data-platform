import asyncio
import json
import unittest
from unittest.mock import patch

import httpx

from agent_runtime import Agent, Settings


def model_json(decision, finish="stop"):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(decision)},
                                                 "finish_reason": finish}]})


def answer_stream(text="测试结果", complete=True):
    chunks = ["data: " + json.dumps({"choices": [{"delta": {"content": char}}]}, ensure_ascii=False)
              + "\n\n" for char in text]
    if complete: chunks.append("data: [DONE]\n\n")
    return httpx.Response(200, content="".join(chunks).encode(), headers={"content-type": "text/event-stream"})


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def make_agent(self, handler, key="fake-key-never-log", settings=None):
        self.tool_calls = []
        def tool(module, focus, params):
            self.tool_calls.append((module, focus, params))
            return '{"value":42}'
        return Agent(key, 'Return JSON', {"food": "餐饮", "jobs": "招聘"}, tool,
                     lambda msg, history: {"reply": "本地答案", "tools": ["food.overview"]},
                     lambda focus: focus, settings=settings,
                     transport=httpx.MockTransport(handler))

    async def collect(self, agent, msg="餐厅价格是多少"):
        return [event async for event in agent.events({"message": msg})]

    async def test_greeting_skips_model(self):
        def handler(req): self.fail("Greeting made a model request")
        result = await self.collect(self.make_agent(handler), "你好！")
        self.assertEqual(result[-1]["source"], "local")

    async def test_missing_key(self):
        def handler(req): self.fail("Missing key made a request")
        result = await self.collect(self.make_agent(handler, key=""))
        self.assertEqual(result[-1]["fallback_reason"], "missing_key")

    async def test_auth_error_no_retry_or_secret_in_logs(self):
        calls = []
        def handler(req):
            calls.append(req)
            return httpx.Response(401, text='fake-key-never-log PRIVATE_PROMPT')
        with self.assertLogs("data_platform.agent", level="INFO") as logs:
            result = await self.collect(self.make_agent(handler), "PRIVATE_PROMPT")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result[-1]["fallback_reason"], "http_401")
        self.assertNotIn('fake-key-never-log', '\n'.join(logs.output))
        self.assertNotIn('PRIVATE_PROMPT', '\n'.join(logs.output))
        self.assertIn('"status":401', '\n'.join(logs.output))

    async def test_timeout_no_retry(self):
        calls = []
        def handler(req):
            calls.append(req)
            raise httpx.ReadTimeout("secret text", request=req)
        result = await self.collect(self.make_agent(handler))
        self.assertEqual(len(calls), 1)
        self.assertEqual(result[-1]["fallback_reason"], "upstream_timeout")

    async def test_transient_http_retry(self):
        calls = []
        def handler(req):
            calls.append(req)
            return httpx.Response(503) if len(calls) == 1 else model_json({"action":"final", "reply":"恢复了"})
        result = await self.collect(self.make_agent(handler))
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[-1]["source"], "llm")

    async def test_invalid_plan_json_fallback(self):
        result = await self.collect(self.make_agent(lambda req: model_json([])))
        self.assertEqual(result[-1]["fallback_reason"], "invalid_json")

    async def test_multiple_tools_one_plan_stream_answer(self):
        requests = []
        def handler(req):
            data = json.loads(req.content)
            requests.append(data)
            if data["stream"]: return answer_stream("收入比较")
            return model_json({"action":"call", "calls":[{"module":"food","focus":"price"},
                                                           {"module":"jobs","focus":"cities"}]})
        result = await self.collect(self.make_agent(handler))
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["response_format"], {"type":"json_object"})
        self.assertEqual(len(self.tool_calls), 2)
        self.assertEqual(''.join(x['text'] for x in result if x['type']=='delta'), '收入比较')
        self.assertEqual(result[-1]["source"], "llm")

    async def test_recommendation_keeps_filters(self):
        def handler(req):
            if json.loads(req.content)["stream"]: return answer_stream()
            return model_json({"action":"call", "calls":[{"module":"food","focus":"overview",
                                                          "params":{"district":"丰台区","max_price":100}}]})
        result = await self.collect(self.make_agent(handler), "推荐丰台区100以内的餐厅")
        self.assertEqual(self.tool_calls, [("food","recommend",{"district":"丰台区","max_price":100})])
        self.assertEqual(result[-1]["tools"], ["food.recommend"])

    async def test_incomplete_stream_not_marked_success(self):
        def handler(req):
            if json.loads(req.content)["stream"]: return answer_stream("部分回答", complete=False)
            return model_json({"action":"call", "calls":[{"module":"food","focus":"price"}]})
        result = await self.collect(self.make_agent(handler))
        self.assertTrue(any(x['type']=='delta' for x in result))
        self.assertEqual(result[-1]["source"], "rules")
        self.assertEqual(result[-1]["reply"], "本地答案")
        self.assertEqual(result[-1]["fallback_reason"], "incomplete_stream")

    async def test_whole_request_budget(self):
        async def handler(req):
            await asyncio.sleep(1)
            return model_json({"action":"final","reply":"too late"})
        result = await self.collect(self.make_agent(handler, settings=Settings(total_timeout=.03)))
        self.assertEqual(result[-1]["fallback_reason"], "total_timeout")

    async def test_disconnect_cancels_upstream(self):
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def handler(req):
            entered.set()
            try: await asyncio.sleep(5)
            except asyncio.CancelledError:
                cancelled.set()
                raise
        events = self.make_agent(handler).events({"message":"餐厅价格"})
        await anext(events)  # Planning status.
        await entered.wait()
        await events.aclose()
        self.assertTrue(cancelled.is_set())

    async def test_waiting_for_model_does_not_block_other_requests(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(req):
            entered.set()
            await release.wait()
            return model_json({"action":"final", "reply":"done"})
        agent = self.make_agent(handler)
        slow = asyncio.create_task(self.collect(agent))
        await entered.wait()
        greeting = await asyncio.wait_for(self.collect(agent, '你好'), timeout=.2)
        self.assertEqual(greeting[-1]['source'], 'local')
        release.set()
        await slow

    async def test_invalid_focus_rejected(self):
        agent = self.make_agent(lambda req: model_json({"action":"call","calls":[
            {"module":"food","focus":"unexpected user content"}]}))
        result = await self.collect(agent)
        self.assertEqual(result[-1]['fallback_reason'], 'invalid_focus')
        self.assertEqual(self.tool_calls, [])


class EndpointTests(unittest.TestCase):
    def test_legacy_and_stream_routes(self):
        import app
        from fastapi.testclient import TestClient
        with TestClient(app.app) as client:
            normal = client.post('/api/agent/chat', json={"message":"你好"})
            self.assertEqual(normal.status_code, 200)
            self.assertEqual(normal.json()['source'], 'local')
            stream = client.post('/api/agent/chat/stream', json={"message":"你好"})
            events = [json.loads(line) for line in stream.text.splitlines()]
            self.assertEqual(events[-1]['source'], 'local')
            self.assertIn('application/x-ndjson', stream.headers['content-type'])
            self.assertEqual(client.get('/health').status_code, 200)


if __name__ == '__main__': unittest.main()
