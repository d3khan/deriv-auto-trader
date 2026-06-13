const Stats = {
    contracts: [],

    init() { },

    render() {
        this.updateBalance(App.state.balance);
        this.updateMetrics(App.state);
    },

    updateBalance(v) {
        const el = document.getElementById('stats-balance');
        if (el) el.textContent = Utils.fmtMoney(v);
    },

    updateMetrics(s) {
        const total = s.wins + s.losses;
        const pct = total > 0 ? Math.round(s.wins / total * 100) : 0;
        const plEl = document.getElementById('stats-pl');
        if (plEl) {
            plEl.textContent = (s.sessionPL >= 0 ? '+' : '') + Utils.fmtMoney(s.sessionPL);
            plEl.className = 'card-value ' + (s.sessionPL >= 0 ? 'positive' : 'negative');
        }
        const rateEl = document.getElementById('stats-rate');
        if (rateEl) rateEl.textContent = pct + '%';
        const wlEl = document.getElementById('stats-wl');
        if (wlEl) wlEl.textContent = s.wins + ' wins / ' + s.losses + ' losses';
        const consecEl = document.getElementById('stats-consec');
        if (consecEl) consecEl.textContent = s.consecutiveLosses;
        const winsEl = document.getElementById('stats-wins');
        if (winsEl) winsEl.textContent = s.wins;
        const lossesEl = document.getElementById('stats-losses');
        if (lossesEl) lossesEl.textContent = s.losses;
        const openEl = document.getElementById('stats-open');
        if (openEl) openEl.textContent = s.activeTrades;
    },

    addContract(c) {
        if (!c) return;
        this.contracts.push(c);
        this.renderTable();
    },

    updateContract(c) {
        if (!c || !c.contract_id) return;
        const idx = this.contracts.findIndex(x => x.contract_id === c.contract_id);
        if (idx >= 0) this.contracts[idx] = c;
        else this.contracts.push(c);
        this.renderTable();
    },

    updateContractClosed(id, profit, status) {
        const idx = this.contracts.findIndex(x => x.contract_id === id || x.id === id);
        if (idx >= 0) {
            this.contracts[idx].profit = profit;
            this.contracts[idx].status = status;
        }
        this.renderTable();
    },

    renderTable() {
        const tbody = document.getElementById('contracts-tbody');
        if (!tbody) return;
        if (this.contracts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7">No active contracts. Start the engine to begin trading.</td></tr>';
            return;
        }
        tbody.innerHTML = this.contracts.map(c => {
            const isOpen = c.status === 'open' || !c.status;
            return '<tr>' +
                '<td>' + (c.contract_id || c.id || '-') + '</td>' +
                '<td>' + (c.contract_type || '-') + '</td>' +
                '<td>' + Utils.fmtMoney(c.stake || 0.35) + '</td>' +
                '<td>' + (c.entry_price || '-') + '</td>' +
                '<td>' + (c.current_price || '-') + '</td>' +
                '<td>' + (c.profit !== undefined ? (c.profit > 0 ? '+' : '') + Utils.fmtMoney(c.profit) : '-') + '</td>' +
                '<td><span class="badge ' + (isOpen ? 'badge-open' : 'badge-closed') + '">' + (isOpen ? 'Open' : 'Closed') + '</span></td>' +
                '</tr>';
        }).join('');
    },

    resetContracts(openContracts) {
        this.contracts = openContracts ? [...openContracts] : [];
        this.renderTable();
    },

    clear() {
        this.contracts = [];
        this.renderTable();
    },

    updateFromServer(stats) { }
};