(() => {
  let socket, retry = 1000, timer, dirty = false, refreshing = false;
  document.addEventListener('input', () => { dirty = true; });
  document.addEventListener('htmx:afterSwap', () => { dirty = false; });
  async function refresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      const response = await fetch(location.href, {headers: {'X-Live-Refresh': '1'}});
      if (response.redirected && response.url.includes('/login/')) { location.assign('/login/'); return; }
      if (!response.ok) return;
      const html = new DOMParser().parseFromString(await response.text(), 'text/html');
      const badge = document.querySelector('#notification-badge');
      const freshBadge = html.querySelector('#notification-badge');
      if (badge && freshBadge) badge.replaceWith(freshBadge);
      if (dirty) {
        document.querySelector('#live-status').textContent = 'Updates available. Finish editing, then refresh to see them.';
      } else {
        const dashboard = document.querySelector('#dashboard-content');
        const freshDashboard = html.querySelector('#dashboard-content');
        if (dashboard && freshDashboard) dashboard.replaceWith(freshDashboard);
        else if (html.querySelector('#main')) document.querySelector('#main').replaceWith(html.querySelector('#main'));
        htmx.process(document.querySelector('#main'));
        document.querySelector('#live-status').textContent = '';
      }
    } finally { refreshing = false; }
  }
  function connect() {
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/household/`);
    socket.onopen = () => { retry = 1000; refresh(); };
    socket.onmessage = event => {
      if (JSON.parse(event.data).type === 'refresh') { clearTimeout(timer); timer = setTimeout(refresh, 100); }
    };
    socket.onclose = event => {
      if (event.code === 4401) { location.assign('/login/'); return; }
      document.querySelector('#live-status').textContent = 'Reconnecting to live updates…';
      setTimeout(connect, retry); retry = Math.min(retry * 2, 30000);
    };
  }
  setInterval(() => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({type: 'ping'})); }, 60000);
  connect();
})();
