// Dependency-free chat interaction regression checks: node tests/test_agent_frontend.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class Element {
  constructor() { this.children = []; this.events = {}; this.value = ''; this._text = ''; this.dataset = {}; }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text + this.children.map(x => x.textContent).join(''); }
  appendChild(child) { this.children.push(child); }
  replaceChildren() { this.children = []; this._text = ''; }
  addEventListener(name, callback) { this.events[name] = callback; }
  focus() {}
  get innerHTML() { return ''; }
  set innerHTML(value) { this.children = []; }
}

function setup(fetch) {
  const elements = Object.fromEntries(['chatbox', 'userInput', 'sendBtn', 'resetBtn'].map(k => [k, new Element()]));
  const context = {
    document: { getElementById: id => elements[id], createElement: () => new Element(), querySelectorAll: () => [] },
    fetch, AbortController, TextDecoder, Uint8Array, Date, setTimeout, clearTimeout, setInterval, clearInterval,
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/agent.js'), 'utf8'), context);
  return { elements, async send(message) { elements.userInput.value = message; await elements.sendBtn.events.click(); } };
}

function response(events) {
  const bytes = new TextEncoder().encode(events.map(e => JSON.stringify(e)).join('\n') + '\n');
  let index = 0;
  const body = new ReadableStream({ pull(controller) {
    if (index >= bytes.length) { controller.close(); return; }
    // Split multibyte Chinese characters and JSON lines across network chunks.
    controller.enqueue(bytes.slice(index, index += 7));
  } });
  return { ok: true, body };
}

(async () => {
  const payloads = [];
  const chat = setup(async (url, options) => {
    assert.equal(url, '/api/agent/chat/stream');
    payloads.push(JSON.parse(options.body));
    return response([
      {type:'status', message:'查询中'},
      {type:'delta', text:'北京', tools:['food.price']},
      {type:'delta', text:'价格'},
      {type:'done', reply:'北京价格', source:'llm', tools:['food.price']},
    ]);
  });
  await chat.send('价格是多少');
  assert.equal(chat.elements.chatbox.children[1].textContent, '🛠 food.price北京价格AI 回答');
  assert.equal(chat.elements.sendBtn.textContent, '发送');
  await chat.send('再看看');
  assert.deepEqual(payloads[1].history, [
    {role:'user', content:'价格是多少'}, {role:'assistant', content:'北京价格'},
  ]);

  const fallback = setup(async () => response([
    {type:'delta', text:'不完整的模型回答'},
    {type:'done', reply:'本地正确结果', source:'rules', tools:['food.overview'], fallback_reason:'upstream_timeout'},
  ]));
  await fallback.send('分析数据');
  const fallbackText = fallback.elements.chatbox.children[1].textContent;
  assert(!fallbackText.includes('不完整的模型回答'));
  assert(fallbackText.includes('本次使用本地分析回答'));

  let capturedSignal;
  const cancel = setup(async (url, options) => {
    capturedSignal = options.signal;
    return new Promise((resolve, reject) => {
      options.signal.addEventListener('abort', () => {
        const error = new Error('aborted'); error.name = 'AbortError'; reject(error);
      });
    });
  });
  const running = cancel.send('需要保留的问题');
  await Promise.resolve();
  await cancel.elements.sendBtn.events.click();
  await running;
  assert(capturedSignal.aborted);
  assert.equal(cancel.elements.userInput.value, '需要保留的问题');
  assert(cancel.elements.chatbox.children[1].textContent.includes('已停止回答'));
  console.log('PASS: UTF-8 streaming, conversation history, fallback replacement, cancellation');
})().catch(error => { console.error(error); process.exitCode = 1; });
