const Chart = {
    timeframe: '1m',
    ticks: [],
    candles: [],
    maxTicks: 200,
    maxCandles: 60,

    init() {
        document.querySelectorAll('.chart-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.timeframe = btn.dataset.tf;
                document.querySelectorAll('.chart-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.draw();
            });
        });
        window.addEventListener('resize', () => {
            if (document.getElementById('chart').classList.contains('active')) this.draw();
        });
    },

    onTick(tick) {
        if (!tick || !tick.quote) return;
        this.ticks.push({ epoch: tick.epoch, price: tick.quote });
        if (this.ticks.length > this.maxTicks) this.ticks.shift();
        this.buildCandles();
        if (document.getElementById('chart').classList.contains('active')) this.draw();
    },

    onCandles(candleData) {
        if (candleData && candleData.candles && Array.isArray(candleData.candles)) {
            const parsed = candleData.candles.map(c => ({
                epoch: c.epoch,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close
            }));
            this.candles = parsed.slice(-this.maxCandles);
        }
    },

    buildCandles() {
        if (this.timeframe === 'ticks') return;
        const granularity = this.timeframe === '1m' ? 60 : 300;
        const grouped = {};
        this.ticks.forEach(t => {
            const bucket = Math.floor(t.epoch / granularity) * granularity;
            if (!grouped[bucket]) grouped[bucket] = [];
            grouped[bucket].push(t.price);
        });
        const newCandles = [];
        Object.keys(grouped).sort((a, b) => parseInt(a) - parseInt(b)).forEach(key => {
            const prices = grouped[key];
            newCandles.push({
                epoch: parseInt(key),
                open: prices[0],
                high: Math.max(...prices),
                low: Math.min(...prices),
                close: prices[prices.length - 1]
            });
        });
        this.candles = newCandles.slice(-this.maxCandles);
    },

    draw() {
        const canvas = document.getElementById('chartCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;

        const styles = getComputedStyle(document.body);
        const cardBg = styles.getPropertyValue('--card-bg').trim();
        const textMuted = styles.getPropertyValue('--text-muted').trim();

        ctx.fillStyle = cardBg;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        if (this.timeframe === 'ticks') this.drawTicks(ctx, styles);
        else this.drawCandles(ctx, styles);

        // Timeframe label
        ctx.fillStyle = textMuted;
        ctx.font = '11px ' + styles.getPropertyValue('--font-mono').trim();
        const label = this.timeframe === 'ticks' ? 'R_10 (Ticks)' : 'R_10 (' + this.timeframe + ')';
        ctx.fillText(label, canvas.width - 110, 20);
    },

    drawTicks(ctx, styles) {
        const accent = styles.getPropertyValue('--accent').trim();
        const success = styles.getPropertyValue('--success').trim();
        const danger = styles.getPropertyValue('--danger').trim();
        const textMuted = styles.getPropertyValue('--text-muted').trim();

        if (this.ticks.length < 2) {
            ctx.fillStyle = textMuted;
            ctx.font = '14px ' + styles.getPropertyValue('--font-mono').trim();
            ctx.fillText('Waiting for live tick data...', canvas.width / 2 - 100, canvas.height / 2);
            return;
        }

        // Grid
        ctx.strokeStyle = textMuted;
        ctx.globalAlpha = 0.08;
        for (let i = 1; i < 5; i++) {
            const y = (canvas.height / 5) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;

        const prices = this.ticks.map(t => t.price);
        const min = Math.min(...prices);
        const max = Math.max(...prices);
        const range = max - min || 1;
        const pad = 50;

        // Draw connecting line
        ctx.beginPath();
        ctx.strokeStyle = accent;
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        this.ticks.forEach((t, i) => {
            const x = pad + (i / (this.ticks.length - 1)) * (canvas.width - pad * 2);
            const y = pad + (max - t.price) / range * (canvas.height - pad * 2);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Draw dots + glow
        this.ticks.forEach((t, i) => {
            const x = pad + (i / (this.ticks.length - 1)) * (canvas.width - pad * 2);
            const y = pad + (max - t.price) / range * (canvas.height - pad * 2);
            const prev = i > 0 ? this.ticks[i - 1].price : t.price;
            const color = t.price >= prev ? success : danger;

            // Glow
            ctx.shadowColor = color;
            ctx.shadowBlur = 8;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.shadowBlur = 0;

            // Inner white dot
            ctx.fillStyle = '#fff';
            ctx.beginPath();
            ctx.arc(x, y, 1.5, 0, Math.PI * 2);
            ctx.fill();
        });

        // Price labels
        ctx.fillStyle = textMuted;
        ctx.font = '11px ' + styles.getPropertyValue('--font-mono').trim();
        ctx.fillText(max.toFixed(3), 8, pad);
        ctx.fillText(min.toFixed(3), 8, canvas.height - pad);
    },

    drawCandles(ctx, styles) {
        const success = styles.getPropertyValue('--success').trim();
        const danger = styles.getPropertyValue('--danger').trim();
        const textMuted = styles.getPropertyValue('--text-muted').trim();

        if (this.candles.length < 2) {
            ctx.fillStyle = textMuted;
            ctx.font = '14px ' + styles.getPropertyValue('--font-mono').trim();
            ctx.fillText('Building candles from tick stream...', canvas.width / 2 - 130, canvas.height / 2);
            return;
        }

        // Grid
        ctx.strokeStyle = textMuted;
        ctx.globalAlpha = 0.08;
        for (let i = 1; i < 5; i++) {
            const y = (canvas.height / 5) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
        ctx.globalAlpha = 1;

        const min = Math.min(...this.candles.map(c => c.low));
        const max = Math.max(...this.candles.map(c => c.high));
        const range = max - min || 1;
        const pad = 50;
        const gap = 2;
        const candleWidth = Math.max(3, (canvas.width - pad * 2) / this.candles.length - gap);

        this.candles.forEach((c, i) => {
            const x = pad + i * (candleWidth + gap) + candleWidth / 2;
            const yOpen = pad + (max - c.open) / range * (canvas.height - pad * 2);
            const yClose = pad + (max - c.close) / range * (canvas.height - pad * 2);
            const yHigh = pad + (max - c.high) / range * (canvas.height - pad * 2);
            const yLow = pad + (max - c.low) / range * (canvas.height - pad * 2);

            const isGreen = c.close >= c.open;
            const color = isGreen ? success : danger;

            // Wick
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(x, yHigh);
            ctx.lineTo(x, yLow);
            ctx.stroke();

            // Body
            const bodyTop = Math.min(yOpen, yClose);
            const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
            ctx.fillStyle = color;
            ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);

            // Glow on latest candle
            if (i === this.candles.length - 1) {
                ctx.shadowColor = color;
                ctx.shadowBlur = 10;
                ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
                ctx.shadowBlur = 0;
            }
        });

        // Price labels
        ctx.fillStyle = textMuted;
        ctx.font = '11px ' + styles.getPropertyValue('--font-mono').trim();
        ctx.fillText(max.toFixed(3), 8, pad);
        ctx.fillText(min.toFixed(3), 8, canvas.height - pad);
    }
};