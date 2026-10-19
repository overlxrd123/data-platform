(() => {
  const app = document.getElementById('app');
  if (!app) return;
  function enhance() {
    const head = app.querySelector('.page-head');
    if (!head || app.querySelector('.section-nav')) return;
    const panels = [...app.querySelectorAll('section.panel')];
    const nav = document.createElement('nav');
    nav.className = 'section-nav';
    nav.setAttribute('aria-label', '分析章节');
    panels.forEach((panel, index) => {
      const title = panel.querySelector('h2');
      if (!title) return;
      panel.id = `analysis-section-${index}`;
      const a = document.createElement('a');
      a.href = `#${panel.id}`;
      a.textContent = title.textContent.split(/[：:？?]/)[0];
      nav.appendChild(a);
      const chart = panel.querySelector('.chart');
      if (chart) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chart-export';
        button.textContent = '导出图表 ↗';
        button.setAttribute('aria-label', `导出${title.textContent}图表`);
        button.addEventListener('click', () => {
          const instance = window.echarts && echarts.getInstanceByDom(chart);
          if (!instance) return;
          const link = document.createElement('a');
          link.download = `${title.textContent.replace(/[\\/:*?"<>|]/g, '-')}.png`;
          link.href = instance.getDataURL({type: 'png', pixelRatio: 2, backgroundColor: '#141e2a'});
          link.click();
        });
        panel.querySelector('.panel-head').appendChild(button);
      }
    });
    head.after(nav);
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        nav.querySelectorAll('a').forEach(a => a.classList.toggle('active', a.hash === `#${entry.target.id}`));
      });
    }, {rootMargin: '-100px 0px -55% 0px', threshold: 0});
    panels.forEach(p => observer.observe(p));
  }
  const observer = new MutationObserver(enhance);
  observer.observe(app, {childList: true});
  enhance();
})();
