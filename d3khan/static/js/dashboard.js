const Dashboard = {
    init() {
        document.getElementById('btn-start').addEventListener('click', () => this.startEngine());
        document.getElementById('btn-stop').addEventListener('click', () => this.stopEngine());
        document.getElementById('stake-input').addEventListener('change', (e) => {
            App.state.stake = parseFloat(e.target.value) || 0.35;
            document.getElementById('opt-stake').value = App.state.stake.toFixed(2);
        });
    },

    render() {
        this.updateBalance(App.state.balance);
        this.updatePL(App.state.sessionPL);
        this.updateTrades(App.state.totalTrades);
        this.updateActive(App.state.activeTrades);
        this.updateWinRate(App.state.wins, App.state.losses);
        this.updateEngineStatus(App.state.engineRunning, App.state.tradingEnabled);
    },

    startEngine() {
        if (App.state.tradingEnabled) return;
        App.send({ action: 'toggle_trading', enabled: true });
    },

    stopEngine() {
        if (!App.state.tradingEnabled) return;
        App.send({ action: 'toggle_trading', enabled: false });
    },

    updateBalance(v) {
        const el = document.getElementById('dash-balance');
        if (el) el.textContent = Utils.fmtMoney(v);
    },

    updatePL(v) {
        const el = document.getElementById('dash-pl');
        if (el) {
            el.textContent = (v >= 0 ? '+' : '') + Utils.fmtMoney(v);
            el.className = 'card-value ' + (v >= 0 ? 'positive' : 'negative');
        }
    },

    updateTrades(v) {
        const el = document.getElementById('dash-trades');
        if (el) el.textContent = v;
    },

    updateActive(v) {
        const el = document.getElementById('dash-active');
        if (el) el.textContent = v;
    },

    updateWinRate(wins, losses) {
        const total = wins + losses;
        const pct = total > 0 ? Math.round(wins / total * 100) : 0;
        const ring = document.getElementById('winRateRing');
        const text = document.getElementById('winRateText');
        if (ring) ring.setAttribute('stroke-dashoffset', 251.2 - (251.2 * pct / 100));
        if (text) text.textContent = pct + '%';
    },

    updateEngineStatus(running, enabled) {
        const dot = document.getElementById('engine-dot');
        const text = document.getElementById('engine-text');
        if (!dot || !text) return;
        if (enabled) {
            dot.classList.remove('offline');
            text.textContent = 'Engine Running';
            text.style.color = 'var(--success)';
        } else {
            dot.classList.add('offline');
            text.textContent = running ? 'Running • Trading OFF' : 'Engine Stopped';
            text.style.color = running ? 'var(--text-muted)' : 'var(--danger)';
        }
    },

    addLog(level, message) {
        const stream = document.getElementById('dash-log');
        if (!stream) return;
        const time = new Date().toLocaleTimeString('en-GB');
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = '<span class="log-time">' + time + '</span><span class="log-' + level + '">' + message + '</span>';
        stream.insertBefore(entry, stream.firstChild);
        while (stream.children.length > 50) stream.removeChild(stream.lastChild);
    }
};