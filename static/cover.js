(() => {
  const canvas = document.getElementById('dataSphere');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  // A deterministic Fibonacci sphere: decorative geometry, not business metrics.
  const points = Array.from({length: 1100}, (_, i) => {
    const y = 1 - (i / 1099) * 2;
    const radius = Math.sqrt(1 - y * y);
    const angle = Math.PI * (3 - Math.sqrt(5)) * i;
    return [Math.cos(angle) * radius, y, Math.sin(angle) * radius];
  });
  let width = 0, height = 0, frame = 0, last = 0;
  const start = performance.now();
  function draw(time) {
    ctx.clearRect(0, 0, width, height);
    const rotation = reduced.matches ? .45 : (time - start) * .000055 + .45;
    const radius = Math.min(width, height) * .345;
    const cos = Math.cos(rotation), sin = Math.sin(rotation);
    const projected = points.map(([x, y, z]) => {
      const rx = x * cos + z * sin;
      const rz = -x * sin + z * cos;
      const ty = y * .95 - rz * .31;
      const tz = y * .31 + rz * .95;
      return {x: width / 2 + rx * radius, y: height / 2 + ty * radius, z: tz};
    }).sort((a,b) => a.z - b.z);
    projected.forEach((p, i) => {
      const depth = (p.z + 1) / 2;
      ctx.fillStyle = `rgba(190,234,159,${.10 + depth * .72})`;
      ctx.beginPath();
      ctx.arc(p.x, p.y, .45 + depth * 1.1, 0, Math.PI * 2);
      ctx.fill();
      if (depth > .6 && i % 9 === 0) {
        const q = projected[i + 3];
        if (q && Math.hypot(q.x - p.x, q.y - p.y) < radius * .23) {
          ctx.strokeStyle = 'rgba(176,219,150,.10)';
          ctx.lineWidth = .5;
          ctx.beginPath(); ctx.moveTo(p.x,p.y); ctx.lineTo(q.x,q.y); ctx.stroke();
        }
      }
    });
  }
  function tick(time) {
    if (time - last > 32) { draw(time); last = time; }
    frame = requestAnimationFrame(tick);
  }
  function sync() {
    cancelAnimationFrame(frame);
    if (!document.hidden && !reduced.matches) frame = requestAnimationFrame(tick);
    else draw(performance.now());
  }
  function resize() {
    const rect = canvas.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = rect.width; height = rect.height;
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw(performance.now());
  }
  new ResizeObserver(resize).observe(canvas);
  document.addEventListener('visibilitychange', sync);
  reduced.addEventListener('change', sync);
  resize(); sync();
})();
