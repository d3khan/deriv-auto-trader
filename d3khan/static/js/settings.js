const Settings = {
    init() {
        this.bindEvents();
        this.loadToggles();
        this.loadLogLevel();
        this.updateCacheSize();
    },

    bindEvents() {
        const themeSel = document.getElementById('theme-selector');
        if (themeSel) {
            themeSel.addEventListener('change', (e) => {
                const theme = e.target.value;
                document.body.setAttribute('data-theme', theme);
                localStorage.setItem('d3khan-theme', theme);
                if (typeof App !== 'undefined') App.setFavicon(theme);
            });
        }

        const sound = document.getElementById('toggle-sound');
        const notif = document.getElementById('toggle-notif');
        const restart = document.getElementById('toggle-restart');

        if (sound) sound.addEventListener('click', () => {
            sound.classList.toggle('active');
            const on = sound.classList.contains('active');
            localStorage.setItem('d3khan-sound', on ? 'true' : 'false');
            if (typeof App !== 'undefined') App.state.soundEnabled = on;
        });

        if (notif) notif.addEventListener('click', () => {
            notif.classList.toggle('active');
            const on = notif.classList.contains('active');
            localStorage.setItem('d3khan-notif', on ? 'true' : 'false');
            if (typeof App !== 'undefined') App.state.notifEnabled = on;
        });

        if (restart) restart.addEventListener('click', () => {
            restart.classList.toggle('active');
            const on = restart.classList.contains('active');
            localStorage.setItem('d3khan-restart', on ? 'true' : 'false');
            if (typeof App !== 'undefined') App.state.autoRestart = on;
        });

        const logLevel = document.getElementById('log-level');
        if (logLevel) {
            logLevel.addEventListener('change', () => {
                const raw = logLevel.value || '';
                const level = raw.split(' ')[0].toLowerCase();
                localStorage.setItem('d3khan-loglevel', level);
                if (typeof Logs !== 'undefined' && Logs.level !== undefined) {
                    Logs.level = level;
                }
            });
        }

        const clearCache = document.getElementById('btn-clear-cache');
        if (clearCache) clearCache.addEventListener('click', async () => {
            clearCache.disabled = true;
            const originalText = clearCache.textContent;
            clearCache.textContent = 'Clearing...';
            try {
                if (typeof App !== 'undefined' && App.send) {
                    App.send({ action: 'clear_cache' });
                }
                localStorage.removeItem('d3khan-options');
                if (typeof Logs !== 'undefined' && Logs.clear) Logs.clear();
                setTimeout(() => {
                    if (typeof App !== 'undefined' && App.send) {
                        App.send({ action: 'get_stats' });
                    }
                }, 200);
                this.updateCacheSize();
                if (typeof Utils !== 'undefined') Utils.toast('Cache cleared', 'success');
            } catch (e) {
                console.error('Clear cache error:', e);
                if (typeof Utils !== 'undefined') Utils.toast('Clear cache failed', 'error');
            } finally {
                clearCache.disabled = false;
                clearCache.textContent = originalText;
            }
        });

        const restartWs = document.getElementById('btn-restart-ws');
        if (restartWs) restartWs.addEventListener('click', () => {
            if (typeof App !== 'undefined') {
                clearTimeout(App.reconnectTimer);
                App.reconnectTimer = null;
                App._manualClose = true;
                if (App.ws) {
                    App.ws.close();
                }
                setTimeout(() => App.initWebSocket(), 500);
            }
        });
    },

    loadToggles() {
        const sound = document.getElementById('toggle-sound');
        const notif = document.getElementById('toggle-notif');
        const restart = document.getElementById('toggle-restart');

        const soundOn = localStorage.getItem('d3khan-sound') === 'true';
        const notifOn = localStorage.getItem('d3khan-notif') === 'true';
        const restartOn = localStorage.getItem('d3khan-restart') === 'true';

        if (sound) {
            sound.classList.toggle('active', soundOn);
            if (typeof App !== 'undefined') App.state.soundEnabled = soundOn;
        }
        if (notif) {
            notif.classList.toggle('active', notifOn);
            if (typeof App !== 'undefined') App.state.notifEnabled = notifOn;
        }
        if (restart) {
            restart.classList.toggle('active', restartOn);
            if (typeof App !== 'undefined') App.state.autoRestart = restartOn;
        }
    },

    loadLogLevel() {
        const logLevel = document.getElementById('log-level');
        const saved = localStorage.getItem('d3khan-loglevel');
        if (logLevel && saved) {
            const options = Array.from(logLevel.options);
            const match = options.find(o => o.value.toLowerCase().startsWith(saved));
            if (match) logLevel.value = match.value;
        }
        if (typeof Logs !== 'undefined' && Logs.level !== undefined && saved) {
            Logs.level = saved;
        }
    },

    async updateCacheSize() {
        const el = document.getElementById('cache-size');
        if (!el) return;
        try {
            const res = await fetch('/api/cache-size');
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const data = await res.json();
            el.textContent = this.formatBytes(data.cache_size_bytes || 0);
        } catch (e) {
            el.textContent = '0 B';
        }
    },

    formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
};