const Options = {
    init() {
        this.bindEvents();
        this.loadFromStorage();
    },

    bindEvents() {
        const ids = ['contract-type', 'opt-stake', 'max-loss', 'max-consec', 'tp-target', 'duration-select'];
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', () => this.onChange());
        });

        // Sync dashboard quick stake override
        const quickStake = document.getElementById('stake-input');
        if (quickStake) {
            quickStake.addEventListener('change', () => {
                const optStake = document.getElementById('opt-stake');
                if (optStake) optStake.value = quickStake.value;
                this.onChange();
            });
        }
    },

    onChange() {
        this.syncStake();
        this.sendUpdate();
        this.saveToStorage();
    },

    syncStake() {
        const quick = document.getElementById('stake-input');
        const opt = document.getElementById('opt-stake');
        if (quick && opt) {
            if (document.activeElement === quick) opt.value = quick.value;
            else if (document.activeElement === opt) quick.value = opt.value;
        }
    },

    sendUpdate() {
        const contractType = document.getElementById('contract-type')?.value || 'ACCU';
        const stake = parseFloat(document.getElementById('opt-stake')?.value) || 1.0;
        const maxLoss = parseFloat(document.getElementById('max-loss')?.value) || 1.0;
        const maxConsec = parseInt(document.getElementById('max-consec')?.value) || 3;
        const tpTarget = parseFloat(document.getElementById('tp-target')?.value) || 0.25;

        if (typeof App !== 'undefined' && App.send) {
            App.send({
                action: 'set_options',
                options: {
                    contract_type: contractType,
                    stake: stake,
                    max_loss: maxLoss,
                    max_consec: maxConsec,
                    tp_target: tpTarget
                }
            });
        }
    },

    saveToStorage() {
        const data = {};
        ['contract-type', 'opt-stake', 'max-loss', 'max-consec', 'tp-target', 'duration-select', 'stake-input'].forEach(id => {
            const el = document.getElementById(id);
            if (el) data[id] = el.value;
        });
        localStorage.setItem('d3khan-options', JSON.stringify(data));
    },

    loadFromStorage() {
        const raw = localStorage.getItem('d3khan-options');
        if (!raw) return;
        try {
            const data = JSON.parse(raw);
            Object.keys(data).forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = data[id];
            });
        } catch (e) {}
    }
};