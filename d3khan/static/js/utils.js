const Utils = {
    toast(msg, type='info', duration=4000) {
        const c = document.getElementById('toastContainer');
        const t = document.createElement('div');
        t.className = 'toast ' + type;
        t.innerHTML = '<span>' + msg + '</span>';
        t.onclick = () => t.remove();
        c.appendChild(t);
        setTimeout(() => t.remove(), duration);
    },

    async requestNotificationPermission() {
        if (!('Notification' in window)) return false;
        const perm = await Notification.requestPermission();
        return perm === 'granted';
    },

    sendDesktopNotif(title, body) {
        if (!('Notification' in window) || Notification.permission !== 'granted') return;
        try {
            new Notification(title, { body, tag: 'd3khan-' + Date.now(), icon: document.getElementById('favicon').href });
        } catch (e) { console.warn('Notification failed', e); }
    },

    fmtMoney(n) {
        return '$' + (Number(n) || 0).toFixed(2);
    },

    fmtPct(n) {
        return Math.round(Number(n) || 0) + '%';
    },

    updateBadge(count) {
        const badge = document.getElementById('notifBadge');
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }
};