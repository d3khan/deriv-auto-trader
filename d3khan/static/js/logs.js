const Logs = {
    entries: [],

    init() {
        document.getElementById('btn-clear-logs')?.addEventListener('click', () => this.clear());
        document.getElementById('btn-export-logs')?.addEventListener('click', () => this.export());
    },

    add(level, message, source, timestamp) {
        const time = timestamp ? new Date(timestamp).toLocaleTimeString('en-GB') : new Date().toLocaleTimeString('en-GB');
        const html = '<div class="log-entry"><span class="log-time">' + time + '</span><span class="log-' + level + '">[' + (source || 'engine') + '] ' + message + '</span></div>';
        this.entries.push(html);
        const full = document.getElementById('full-logs');
        if (full) {
            full.insertBefore(this.htmlToElement(html), full.firstChild);
            while (full.children.length > 100) full.removeChild(full.lastChild);
        }
    },

    htmlToElement(html) {
        const div = document.createElement('div');
        div.innerHTML = html.trim();
        return div.firstChild;
    },

    clear() {
        this.entries = [];
        const full = document.getElementById('full-logs');
        if (full) full.innerHTML = '<div class="log-entry"><span class="log-time">' + new Date().toLocaleTimeString('en-GB') + '</span><span class="log-system">[SYS] Logs cleared by user.</span></div>';
        Utils.toast('Logs cleared', 'info');
    },

    export() {
        const blob = new Blob([this.entries.join('\n')], { type: 'text/plain' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'd3khan_logs_' + Date.now() + '.txt';
        a.click();
        Utils.toast('Logs exported', 'success');
    }
};