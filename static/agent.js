/* Stream answers; model content is always rendered as text, never HTML. */
(function () {
  const box = document.getElementById('chatbox');
  const input = document.getElementById('userInput');
  const btn = document.getElementById('sendBtn');
  const reset = document.getElementById('resetBtn');
  let history = [], busy = false, controller = null;
  const welcome = box.innerHTML;

  function append(role, text) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
  }

  function renderAnswer(node, text, tools, notice) {
    node.className = 'msg agent';
    node.replaceChildren();
    if (tools && tools.length) {
      const trace = document.createElement('div');
      trace.className = 'tools';
      trace.textContent = `🛠 ${tools.join(' → ')}`;
      node.appendChild(trace);
    }
    const body = document.createElement('span');
    body.textContent = text;
    node.appendChild(body);
    if (notice) {
      const label = document.createElement('div');
      label.className = 'agent-source';
      label.textContent = notice;
      node.appendChild(label);
    }
    box.scrollTop = box.scrollHeight;
  }

  async function send() {
    if (busy) { if (controller) controller.abort(); return; }
    const msg = input.value.trim();
    if (!msg) return;
    busy = true;
    reset.disabled = true;
    document.querySelectorAll('.suggestions button').forEach(b => b.disabled = true);
    btn.textContent = '停止';
    input.value = '';
    append('user', msg);
    const pending = append('agent loading', '正在连接分析助手…');
    const priorHistory = history.slice(-8);
    history.push({ role: 'user', content: msg });
    controller = new AbortController();
    const requestController = controller, started = Date.now();
    let status = '正在连接分析助手…', reply = '', tools = [], done = false, timedOut = false, reader;
    const ticker = setInterval(() => {
      if (!reply && !done) pending.textContent = `${status}（已等待 ${Math.floor((Date.now()-started)/1000)} 秒）`;
    }, 1000);
    // Allows for Render cold starts as well as the separate backend processing budget.
    const limit = setTimeout(() => { timedOut = true; requestController.abort(); }, 120000);

    function handle(event) {
      if (done) return;
      if (event.type === 'status') {
        status = event.message;
        if (event.tools) tools = event.tools;
        if (!reply) pending.textContent = status;
      } else if (event.type === 'delta') {
        reply += event.text || '';
        if (event.tools) tools = event.tools;
        renderAnswer(pending, reply, tools);
      } else if (event.type === 'done') {
        done = true;
        // Fallback replaces incomplete model text instead of mixing two answers.
        reply = event.reply || '（没有返回内容）';
        tools = event.tools || [];
        const notice = event.source === 'rules'
          ? (event.fallback_reason === 'missing_key' ? '本地分析回答' : 'AI 暂时未能完成，本次使用本地分析回答')
          : event.source === 'llm' ? 'AI 回答' : '';
        renderAnswer(pending, reply, tools, notice);
      }
    }

    try {
      const res = await fetch('/api/agent/chat/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history: priorHistory }), signal: requestController.signal
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error('浏览器不支持流式响应');
      reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (!done) {
        const chunk = await reader.read();
        buffer += decoder.decode(chunk.value || new Uint8Array(), { stream: !chunk.done });
        let end;
        while ((end = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, end).trim();
          buffer = buffer.slice(end + 1);
          if (line) handle(JSON.parse(line));
        }
        if (chunk.done) { if (buffer.trim()) handle(JSON.parse(buffer)); break; }
      }
      if (!done) throw new Error('连接中断，回答未完成');
      history.push({ role: 'assistant', content: reply });
      if (history.length > 16) history = history.slice(-16);
    } catch (e) {
      history.pop();
      input.value = msg;
      const reason = e.name === 'AbortError'
        ? (timedOut ? '等待超时，请稍后重试' : '已停止回答') : `暂时未能完成分析（${e.message}）`;
      renderAnswer(pending, `${reason}，问题已保留。`, [], '');
    } finally {
      clearInterval(ticker); clearTimeout(limit);
      if (reader) {
        try { await reader.cancel(); } catch (_) { /* Already closed or aborted. */ }
        reader.releaseLock();
      }
      controller = null; busy = false;
      reset.disabled = false;
      document.querySelectorAll('.suggestions button').forEach(b => b.disabled = false);
      btn.textContent = '发送'; input.focus();
    }
  }

  btn.addEventListener('click', send);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); if (!busy) send(); }
  });
  document.querySelectorAll('.suggestions button').forEach(b => {
    b.addEventListener('click', () => { input.value = b.dataset.q || b.textContent; send(); });
  });
  reset.addEventListener('click', () => { history = []; box.innerHTML = welcome; input.focus(); });
  input.focus();
})();
