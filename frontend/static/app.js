// Micro-interactions, keyboard shortcuts, lottie loader, confetti

;(function(){
  const toast = (msg, timeout=1800) => {
    let el = document.querySelector('.toast');
    if (!el) {
      el = document.createElement('div');
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(()=> el.classList.remove('show'), timeout);
  }

  const toggleSidebar = () => {
    const sb = document.querySelector('[data-testid="stSidebar"]');
    if (!sb) return toast('Sidebar not found');
    const style = sb.style;
    style.display = (style.display === 'none') ? '' : 'none';
    toast(style.display === 'none' ? 'Sidebar hidden' : 'Sidebar shown');
  }

  // Simple confetti
  const confetti = () => {
    let canvas = document.getElementById('confetti-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'confetti-canvas';
      document.body.appendChild(canvas);
    }
    const ctx = canvas.getContext('2d');
    const W = canvas.width = window.innerWidth;
    const H = canvas.height = window.innerHeight;
    const pieces = Array.from({length: 160}).map(()=>({
      x: Math.random()*W,
      y: -20 - Math.random()*H,
      r: 2 + Math.random()*4,
      c: `hsl(${Math.random()*360},80%,60%)`,
      s: 1 + Math.random()*3
    }));
    let t = 0;
    const tick = () => {
      ctx.clearRect(0,0,W,H);
      pieces.forEach(p=>{ p.y += p.s; p.x += Math.sin(t/20 + p.r); if (p.y>H+20) p.y=-20; ctx.fillStyle=p.c; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2); ctx.fill(); });
      t++; if (t<200) requestAnimationFrame(tick); else ctx.clearRect(0,0,W,H);
    }
    tick();
  }

  // Command palette
  const commands = [
    {label: 'Toggle sidebar', action: toggleSidebar, hint: 'Cmd+/'},
    {label: 'Confetti', action: confetti, hint: 'Celebrate'},
    {label: 'Scroll to top', action: () => window.scrollTo({top:0,behavior:'smooth'}), hint: 'Cmd+Up'},
    {label: 'Focus search', action: () => { const el = document.querySelector('input[type="text"]'); if(el) el.focus(); }, hint: 'Focus'},
  ];
  const showPalette = () => {
    let root = document.querySelector('.cmdk');
    if (!root) {
      root = document.createElement('div');
      root.className = 'cmdk';
      root.innerHTML = `
        <div class="panel">
          <div class="header"><input placeholder="Type a command..." /></div>
          <div class="list"></div>
        </div>`;
      document.body.appendChild(root);
    }
    const list = root.querySelector('.list');
    const input = root.querySelector('input');
    const render = (q='') => {
      list.innerHTML = '';
      commands.filter(c => c.label.toLowerCase().includes(q.toLowerCase()))
        .forEach(c => {
          const item = document.createElement('div');
          item.className = 'item';
          item.innerHTML = `<span>${c.label}</span><small style="color:#94a3b8">${c.hint||''}</small>`;
          item.onclick = () => { c.action(); hidePalette(); }
          list.appendChild(item);
        });
    }
    const hidePalette = () => root.remove();
    input.oninput = (e)=> render(e.target.value);
    input.onkeydown = (e)=> { if(e.key==='Escape'){ hidePalette(); } }
    render('');
    input.focus();
  }

  // Keyboard shortcuts
  window.addEventListener('keydown', (e) => {
    const cmd = e.metaKey || e.ctrlKey;
    if (cmd && e.key.toLowerCase() === 'k') { e.preventDefault(); showPalette(); }
    if (cmd && e.key === '/') { e.preventDefault(); toggleSidebar(); }
  });

  // Hook buttons with class .btn-animated for feedback
  document.addEventListener('click', (e)=>{
    const target = e.target.closest('.btn-animated');
    if (target) toast('Action triggered');
  });

  // Expose helpers globally
  window._aim_ui = { toast, confetti, showPalette };
})();