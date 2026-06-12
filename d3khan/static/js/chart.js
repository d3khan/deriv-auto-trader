const Chart = {
    chart: null,
    areaSeries: null,
    barrierUpperSeries: null,
    barrierLowerSeries: null,
    initialized: false,
    libraryReady: false,

    tickData: [],
    maxTicks: 5000,

    barrierUpper: null,
    barrierLower: null,
    barrierActive: false,

    init() {
        this.loadLibrary().then(() => {
            this.libraryReady = true;
            this.createChart();
            this.initialized = true;
        }).catch(err => {
            console.error('[Chart] Library failed:', err);
        });
    },

    loadLibrary() {
        return new Promise((resolve, reject) => {
            if (window.LightweightCharts) return resolve();
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    },

    createChart() {
        const container = document.getElementById('lwChart');
        if (!container) return;

        const styles = getComputedStyle(document.body);
        const bg = styles.getPropertyValue('--bg').trim() || '#0a0a0a';
        const text = styles.getPropertyValue('--text').trim() || '#e0e0e0';
        const grid = styles.getPropertyValue('--text-muted').trim() || '#333';

        this.chart = LightweightCharts.createChart(container, {
            autoSize: true,
            layout: {
                background: { type: 'solid', color: bg },
                textColor: text,
            },
            grid: {
                vertLines: { color: grid + '30', style: LightweightCharts.LineStyle.SparseDotted },
                horzLines: { color: grid + '30', style: LightweightCharts.LineStyle.SparseDotted },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: { color: '#5f636d', width: 1, style: LightweightCharts.LineStyle.Dashed },
                horzLine: { color: '#5f636d', width: 1, style: LightweightCharts.LineStyle.Dashed },
            },
            rightPriceScale: {
                borderColor: grid,
                scaleMargins: { top: 0.15, bottom: 0.15 },
            },
            timeScale: {
                borderColor: grid,
                timeVisible: true,
                secondsVisible: true,
                rightOffset: 50,
                barSpacing: 6,
            },
            handleScroll: { vertTouchDrag: false },
            handleScale: { axisPressedMouseMove: true },
        });

        this.areaSeries = this.chart.addAreaSeries({
            lineColor: '#ffffff',
            topColor: '#00b06b33',
            bottomColor: '#00b06b05',
            lineWidth: 2,
            lastValueVisible: true,
            priceLineVisible: true,
            priceLineColor: '#ffffff',
            priceLineWidth: 1,
            priceLineStyle: LightweightCharts.LineStyle.Dashed,
        });

        this.barrierUpperSeries = this.chart.addLineSeries({
            color: '#2979ff',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            lastValueVisible: false,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
        });

        this.barrierLowerSeries = this.chart.addLineSeries({
            color: '#2979ff',
            lineWidth: 1,
            lineStyle: LightweightCharts.LineStyle.Dotted,
            lastValueVisible: false,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
        });
    },

    onTickHistory(ticks) {
        if (!ticks || ticks.length === 0) return;
        const newData = ticks.map(t => ({ time: t.epoch, value: t.price }));
        this.tickData = newData;
        if (this.areaSeries) {
            this.areaSeries.setData(this.tickData.slice(-2000));
            this.chart.timeScale().fitContent();
        }
    },

    onTick(tick) {
        if (!tick || tick.quote === undefined) return;
        const point = { time: tick.epoch, value: tick.quote };
        this.tickData.push(point);
        if (this.tickData.length > this.maxTicks) this.tickData.shift();

        this.updateBarrierColors(tick.quote);

        if (this.areaSeries) {
            this.areaSeries.update(point);
            this.updateBarrierLines();
        }
    },

    setBarriers(upper, lower) {
        this.barrierUpper = upper;
        this.barrierLower = lower;
        this.barrierActive = (upper !== null && lower !== null);
        if (this.barrierUpperSeries && this.barrierLowerSeries) {
            this.barrierUpperSeries.applyOptions({ visible: this.barrierActive });
            this.barrierLowerSeries.applyOptions({ visible: this.barrierActive });
        }
    },

    updateBarrierColors(currentPrice) {
        if (!this.barrierActive || currentPrice === undefined || !this.areaSeries) return;
        const inside = currentPrice <= this.barrierUpper && currentPrice >= this.barrierLower;

        if (inside) {
            this.areaSeries.applyOptions({
                topColor: '#00b06b33',
                bottomColor: '#00b06b05',
                lineColor: '#ffffff'
            });
        } else {
            this.areaSeries.applyOptions({
                topColor: '#ff444f33',
                bottomColor: '#ff444f05',
                lineColor: '#ff444f'
            });
        }
    },

    updateBarrierLines() {
        if (!this.barrierActive || !this.areaSeries || this.tickData.length < 2) return;

        const visibleData = this.tickData.slice(-200);
        if (visibleData.length < 2) return;

        const firstTime = visibleData[0].time;
        const lastTime = visibleData[visibleData.length - 1].time;
        const futureTime = lastTime + 50;

        const upperData = [
            { time: firstTime, value: this.barrierUpper },
            { time: futureTime, value: this.barrierUpper }
        ];
        const lowerData = [
            { time: firstTime, value: this.barrierLower },
            { time: futureTime, value: this.barrierLower }
        ];

        this.barrierUpperSeries.setData(upperData);
        this.barrierLowerSeries.setData(lowerData);
    },

    resizeAndDraw() {
        if (!this.chart) return;
        this.chart.resize();
        this.chart.timeScale().fitContent();
    }
};