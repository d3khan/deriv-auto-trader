const Settings = {
    init() {
        const themeSel = document.getElementById('theme-selector');
        if (themeSel) {
            themeSel.addEventListener('change', (e) => {
                const t = e.target.value;
                document.body.setAttribute('data-theme', t);
                localStorage.setItem('d3khan-theme', t);
                App.setFavicon(t);
                Utils.toast('Theme switched to ' + t, 'success');
                if (document.getElementById('chart').classList.contains('active')) Chart.draw();
            });
        }

        document.getElementById('toggle-sound')?.addEventListener('click', function() {
            this.classList.toggle('active');
            App.state.soundEnabled = this.classList.contains('active');
        });
        document.getElementById('toggle-notif')?.addEventListener('click', async function() {
            this.classList.toggle('active');
            App.state.notifEnabled = this.classList.contains('active');
            if (App.state.notifEnabled) {
                const ok = await Utils.requestNotificationPermission();
                if (!ok) { this.classList.remove('active'); App.state.notifEnabled = false; Utils.toast('Notification permission denied', 'warning'); }
            }
        });
        document.getElementById('toggle-restart')?.addEventListener('click', function() {
            this.classList.toggle('active');
            App.state.autoRestart = this.classList.contains('active');
        });

        document.getElementById('btn-clear-cache')?.addEventListener('click', () => {
            if (!confirm('Reset all session stats to zero?')) return;
            App.send({ action: 'clear_cache' });
            App.state.sessionPL = 0; App.state.totalTrades = 0; App.state.wins = 0; App.state.losses = 0; App.state.consecutiveLosses = 0;
            Dashboard.render();
            Stats.render();
            Utils.toast('Cache cleared. Stats reset.', 'success');
        });

        document.getElementById('btn-restart-ws')?.addEventListener('click', () => {
            if (App.ws) App.ws.close();
            App.initWebSocket();
            Utils.toast('WebSocket restarting…', 'info');
        });
    }
};