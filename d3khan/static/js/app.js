const App = {
    ws: null,
    state: {
        engineRunning: false, tradingEnabled: false, wsConnected: false, daemonOnline: false,
        balance: 0, sessionPL: 0, totalTrades: 0, activeTrades: 0, wins: 0, losses: 0, consecutiveLosses: 0,
        stake: 1.00, maxLoss: 1.00, maxConsec: 3, tpTarget: 0.25,
        soundEnabled: false, notifEnabled: true, autoRestart: true, logs: [], notifCount: 0,
        demoMode: false, currentStrategy: 'DUMMY_RISE_FALL'
    },
    reconnectTimer: null,
    favicons: {
        void: 'https://kimi-web-img.moonshot.cn/img/cdn-icons-png.flaticon.com/3fbf85e7470b21893f94568921916eabaa1a23be.png',
        ice: 'https://kimi-web-img.moonshot.cn/img/cdn-icons-png.flaticon.com/9059286e1753ab6e77aacba560f4f476f7fae544.png',
        matrix: 'https://kimi-web-img.moonshot.cn/img/static.vecteezy.com/2bc0a5367beb99e016c163192d1cdef95cc49c0c.jpg'
    },

    init() {
        this.initTheme();
        this.initTabs();
        this.initChartTabs();
        this.initWebSocket();
        this.initNotifBell();
        this.initVisibilityListener();
        Dashboard.init();
        Stats.init();
        Chart.init();
        Options.init();
        Settings.init();
        Logs.init();
    },

    initTheme() {
        const saved = localStorage.getItem('d3khan-theme');
        const theme = ['void','ice','matrix'].includes(saved) ? saved : 'void';
        document.body.setAttribute('data-theme', theme);
        this.setFavicon(theme);
        const sel = document.getElementById('theme-selector');
        if (sel) sel.value = theme;
    },

    setFavicon(theme) {
        const link = document.getElementById('favicon');
        if (link && this.favicons[theme]) link.href = this.favicons[theme];
    },

    initTabs() {
        document.querySelectorAll('.tab').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.dataset.tab;
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById(tabId).classList.add('active');
                if (tabId === 'chart') {
                    const activeChart = document.querySelector('.chart-btn.active')?.dataset.chart;
                    if (activeChart === 'ticks') {
                        setTimeout(() => Chart.resizeAndDraw(), 150);
                    }
                }
            });
        });
    },

    initChartTabs() {
        document.querySelectorAll('.chart-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const sub = btn.dataset.chart;
                if (!sub) return;
                document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('chart-ticks').style.display = sub === 'ticks' ? 'block' : 'none';
                document.getElementById('chart-candles').style.display = sub === 'candles' ? 'block' : 'none';
                if (sub === 'ticks') {
                    setTimeout(() => Chart.resizeAndDraw(), 150);
                }
            });
        });
    },

    initWebSocket() {
        const url = (location.protocol === 'https:' ? 'wss' : 'ws') + '://' + location.host + '/ws';
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this.state.wsConnected = true;
            this.updateConnectionStatus(true);
            Utils.toast('WebSocket connected', 'success');
            this.send({ action: 'ping' });

            const contractType = document.getElementById('contract-type')?.value || 'ACCU';
            const stake = parseFloat(document.getElementById('opt-stake')?.value) || 1.0;
            const maxLoss = parseFloat(document.getElementById('max-loss')?.value) || 1.0;
            const maxConsec = parseInt(document.getElementById('max-consec')?.value) || 3;
            const tpTarget = parseFloat(document.getElementById('tp-target')?.value) || 0.25;
            this.send({
                action: 'set_options',
                options: {
                    contract_type: contractType,
                    stake: stake,
                    max_loss: maxLoss,
                    max_consec: maxConsec,
                    tp_target: tpTarget
                }
            });
        };

        this.ws.onclose = () => {
            this.state.wsConnected = false;
            this.updateConnectionStatus(false);
            Utils.toast('WebSocket disconnected — retrying…', 'warning');
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = setTimeout(() => this.initWebSocket(), 3000);
        };

        this.ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                this.handleMessage(msg);
            } catch (err) {
                console.error('WS parse error', err);
            }
        };
    },

    initVisibilityListener() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                const activeChart = document.querySelector('.chart-btn.active')?.dataset.chart;
                if (activeChart === 'ticks') {
                    setTimeout(() => Chart.resizeAndDraw(), 150);
                }
            }
        });
    },

    send(obj) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj));
    },

    _updateStatsDOM() {
        const statsPl = document.getElementById('stats-pl');
        if (statsPl) {
            const pl = this.state.sessionPL;
            statsPl.textContent = (pl >= 0 ? '+' : '-') + '$' + Math.abs(pl).toFixed(2);
            statsPl.className = 'card-value ' + (pl >= 0 ? 'positive' : 'negative');
        }
        const statsRate = document.getElementById('stats-rate');
        const statsWl = document.getElementById('stats-wl');
        const total = this.state.wins + this.state.losses;
        const rate = total > 0 ? Math.round(this.state.wins / total * 100) : 0;
        if (statsRate) statsRate.textContent = rate + '%';
        if (statsWl) statsWl.textContent = this.state.wins + ' wins / ' + this.state.losses + ' losses';
        const statsConsec = document.getElementById('stats-consec');
        if (statsConsec) statsConsec.textContent = this.state.consecutiveLosses;
    },

    handleMessage(msg) {
        switch (msg.type) {
            case 'init':
                this.state.demoMode = msg.demo_mode || false;
                const badge = document.getElementById('demo-badge-sidebar');
                if (badge) badge.classList.toggle('hidden', !this.state.demoMode);

                if (msg.version) {
                    const verEl = document.getElementById('engine-version');
                    if (verEl) verEl.textContent = msg.version;
                }
                if (msg.build) {
                    const buildEl = document.getElementById('engine-build');
                    if (buildEl) buildEl.textContent = 'Build ' + msg.build;
                }

                if (msg.state) {
                    const s = msg.state;
                    this.state.balance = (s.balance !== undefined && s.balance !== null) ? s.balance : 0;
                    this.state.sessionPL = (s.session_pl !== undefined && s.session_pl !== null) ? s.session_pl : 0;
                    this.state.totalTrades = s.total_trades || 0;
                    this.state.wins = s.total_wins || 0;
                    this.state.losses = s.total_losses || 0;
                    this.state.activeTrades = (s.open_contracts || []).length;
                    this.state.engineRunning = s.is_running || false;
                    this.state.tradingEnabled = s.is_trading_enabled || false;
                    this.state.consecutiveLosses = 0;
                }
                if (msg.ticks && msg.ticks.length > 0) {
                    Chart.onTickHistory(msg.ticks);
                }
                Dashboard.render();
                Stats.render();
                this._updateStatsDOM();
                break;

            case 'balance':
                this.state.balance = (msg.balance !== undefined && msg.balance !== null) ? msg.balance : 0;
                this.state.sessionPL = (msg.session_pl !== undefined && msg.session_pl !== null) ? msg.session_pl : 0;
                Dashboard.updateBalance(msg.balance);
                Dashboard.updatePL(msg.session_pl);
                Stats.updateBalance(msg.balance);
                this._updateStatsDOM();
                break;

            case 'tick':
                if (msg.barriers) {
                    Chart.setBarriers(msg.barriers.upper, msg.barriers.lower);
                }
                Chart.onTick(msg.tick);
                break;

            case 'trade_opened':
                this.state.activeTrades++;
                Dashboard.updateActive(this.state.activeTrades);
                Stats.addContract(msg.contract);
                Utils.toast('Trade opened: ' + (msg.contract?.contract_type || ''), 'success');
                break;

            case 'trade_closed':
                this.state.activeTrades = Math.max(0, this.state.activeTrades - 1);
                this.state.totalTrades++;
                if (msg.profit > 0) this.state.wins++; else this.state.losses++;
                if (msg.profit <= 0) this.state.consecutiveLosses++; else this.state.consecutiveLosses = 0;
                this.state.sessionPL += msg.profit || 0;
                Dashboard.updateActive(this.state.activeTrades);
                Dashboard.updateTrades(this.state.totalTrades);
                Dashboard.updateWinRate(this.state.wins, this.state.losses);
                Dashboard.updatePL(this.state.sessionPL);
                Stats.updateContractClosed(msg.contract_id, msg.profit, msg.status);
                Stats.updateMetrics(this.state);
                this._updateStatsDOM();
                Utils.toast('Trade closed: ' + (msg.profit > 0 ? '+' : '') + (msg.profit?.toFixed?.(2) || msg.profit), msg.profit > 0 ? 'success' : 'error');
                break;

            case 'contract_update':
                Stats.updateContract(msg.contract);
                break;

            case 'log':
                if (typeof Logs !== 'undefined' && Logs.shouldShow && Logs.shouldShow(msg.level)) {
                    Logs.add(msg.level, msg.message, msg.source, msg.timestamp);
                    Dashboard.addLog(msg.level, msg.message);
                }
                break;

            case 'trading_status':
                this.state.tradingEnabled = msg.enabled;
                Dashboard.updateEngineStatus(this.state.engineRunning, msg.enabled);
                break;

            case 'engine_status':
                this.state.engineRunning = msg.status === 'running';
                Dashboard.updateEngineStatus(this.state.engineRunning, this.state.tradingEnabled);
                break;

            case 'auto_stop':
                this.state.tradingEnabled = false;
                Dashboard.updateEngineStatus(this.state.engineRunning, false);
                Utils.toast('Auto-stop: ' + msg.reason, 'warning');
                Utils.sendDesktopNotif('d3khan Auto-Stop', msg.reason);
                break;

            case 'error':
                Utils.toast(msg.message, 'error');
                break;

            case 'info':
                Utils.toast(msg.message, 'info');
                break;

            case 'stats':
                Stats.updateFromServer(msg.stats);
                break;

            case 'cache_cleared':
                Utils.toast('Server cache and stats reset', 'success');
                break;

            case 'pong':
                break;
        }
    },

    updateConnectionStatus(online) {
        const dots = ['ws-dot', 'ws-dot-sidebar', 'dash-status-dot', 'daemon-dot'];
        const texts = [
            { id: 'ws-text', on: 'Online', off: 'Offline' },
            { id: 'ws-text-sidebar', on: 'Online', off: 'Offline' },
            { id: 'dash-status-text', on: 'Connected', off: 'Disconnected' },
            { id: 'daemon-text', on: 'Daemon Online', off: 'Daemon Offline' }
        ];
        dots.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.toggle('offline', !online);
        });
        texts.forEach(t => {
            const el = document.getElementById(t.id);
            if (el) {
                el.textContent = online ? t.on : t.off;
                el.style.color = online ? 'var(--success)' : 'var(--danger)';
            }
        });
    },

    initNotifBell() {
        const bell = document.getElementById('notifBell');
        if (bell) bell.addEventListener('click', () => {
            Utils.requestNotificationPermission();
        });
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());