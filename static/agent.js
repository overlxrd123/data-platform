/* AI Agent 交互 */
(function () {
  const box = document.getElementById('chatbox');
  const input = document.getElementById('userInput');
  const btn = document.getElementById('sendBtn');
  let history = [];
  let busy = false;
  const welcome = box.innerHTML;

  function append(role, html, tools) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    const trace = tools && tools.length
      ? `<div class="tools">🛠 ${tools.map(t => C.esc(t)).join(' → ')}</div>`
      : '';
    div.innerHTML = trace + html;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
    return div;
  }

  async function send() {
    const msg = input.value.trim();
    if (!msg || busy) return;
    busy = true;
    document.getElementById('resetBtn').disabled = true;
    document.querySelectorAll('.suggestions button').forEach(b => b.disabled = true);
    btn.disabled = true;
    btn.textContent = '思考中…';
    input.value = '';
    append('user', C.esc(msg));
    const pending = append('agent loading', '正在选择模块并调用分析工具…');
    // 后端会单独追加当前 message，这里只发送此前的历史，避免同一问题出现两次
    const priorHistory = history.slice(-8);
    history.push({ role: 'user', content: msg });

    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, history: priorHistory })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      pending.remove();
      append('agent', C.esc(d.reply || '（没有返回内容）'), d.tools);
      history.push({ role: 'assistant', content: d.reply || '' });
      if (history.length > 16) history = history.slice(-16);
    } catch (e) {
      pending.remove();
      history.pop();
      input.value = msg;
      append('agent', `暂时未能完成分析（${C.esc(e.message)}），问题已保留，可重试。`);
    } finally {
      busy = false;
      document.getElementById('resetBtn').disabled = false;
      document.querySelectorAll('.suggestions button').forEach(b => b.disabled = false);
      btn.disabled = false;
      btn.textContent = '发送';
      input.focus();
    }
  }

  btn.addEventListener('click', send);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      send();
    }
  });

  document.querySelectorAll('.suggestions button').forEach(b => {
    b.addEventListener('click', () => {
      input.value = b.dataset.q || b.textContent;
      send();
    });
  });

  const resetBtn = document.getElementById('resetBtn');
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      history = [];
      box.innerHTML = welcome;
      input.value = '';
      input.focus();
    });
  }

  input.focus();
})();
