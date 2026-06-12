const Options = {
    init() {
        const typeSel = document.getElementById('contract-type');
        if (typeSel) typeSel.addEventListener('change', (e) => {
            App.send({ action: 'set_strategy', strategy: e.target.value });
            Utils.toast('Strategy: ' + e.target.value, 'info');
        });
        const stakeIn = document.getElementById('opt-stake');
        if (stakeIn) stakeIn.addEventListener('change', (e) => {
            App.state.stake = parseFloat(e.target.value) || 0.35;
            document.getElementById('stake-input').value = App.state.stake.toFixed(2);
        });
    }
};