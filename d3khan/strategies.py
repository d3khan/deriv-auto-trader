from typing import Optional, Dict, Any

class IndicatorState:
    def __init__(self):
        self.prices = []
        self.ticks = []

    def update(self, tick: dict):
        self.ticks.append(tick)
        self.prices.append(tick["quote"])
        if len(self.prices) > 1000:
            self.prices = self.prices[-1000:]
            self.ticks = self.ticks[-1000:]

    def sma(self, period: int) -> float:
        if len(self.prices) < period:
            return self.prices[-1] if self.prices else 0
        return sum(self.prices[-period:]) / period

    def ema(self, period: int) -> float:
        if len(self.prices) < period:
            return self.prices[-1] if self.prices else 0
        prices = self.prices[-period:]
        multiplier = 2 / (period + 1)
        # Proper SMA seeding — matches TradingView/Deriv
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def rsi(self, period: int = 14) -> float:
        if len(self.prices) < period + 1:
            return 50.0
        deltas = [self.prices[i] - self.prices[i-1] for i in range(-period, 0)]
        gains = sum(d for d in deltas if d > 0)
        losses = sum(-d for d in deltas if d < 0)
        if losses == 0:
            return 100.0
        return 100 - (100 / (1 + gains / losses))

    def bbands(self, period: int = 20, std_dev: float = 2.0) -> dict:
        if len(self.prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0}
        prices = self.prices[-period:]
        middle = sum(prices) / period
        variance = sum((p - middle) ** 2 for p in prices) / period
        std = variance ** 0.5
        return {"upper": middle + std_dev * std, "middle": middle, "lower": middle - std_dev * std}

    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        # Need full history for the signal line to converge
        if len(self.prices) < slow + signal + 50:
            return {"macd": 0, "signal": 0, "histogram": 0}

        def calc_ema_series(data, period):
            if len(data) < period:
                return [data[-1]] if data else [0]
            multiplier = 2 / (period + 1)
            ema = sum(data[:period]) / period
            emas = [ema]
            for value in data[period:]:
                ema = (value - ema) * multiplier + ema
                emas.append(ema)
            return emas

        # Use ALL available prices for proper EMA convergence
        prices = self.prices[:]

        fast_emas = calc_ema_series(prices, fast)
        slow_emas = calc_ema_series(prices, slow)

        # Align fast and slow EMAs at the same price index
        macd_line = []
        fast_offset = slow - fast
        for i in range(len(slow_emas)):
            macd_line.append(fast_emas[fast_offset + i] - slow_emas[i])

        signal_emas = calc_ema_series(macd_line, signal)

        current_macd = macd_line[-1]
        current_signal = signal_emas[-1]

        return {
            "macd": current_macd,
            "signal": current_signal,
            "histogram": current_macd - current_signal
        }

    def donchian(self, period: int = 20) -> dict:
        if len(self.prices) < period:
            return {"upper": 0, "lower": 0, "middle": 0}
        prices = self.prices[-period:]
        upper = max(prices)
        lower = min(prices)
        return {"upper": upper, "lower": lower, "middle": (upper + lower) / 2}


class StrategyEngine:
    def __init__(self, strategy: str = "ACCU"):
        self.strategy = strategy
        self.indicators = IndicatorState()
        self.last_signal = None
        self.tick_count = 0
        self.last_direction = "CALL"

    def update(self, tick: dict):
        self.indicators.update(tick)
        self.tick_count += 1

    def get_signal(self) -> Optional[Dict[str, Any]]:
        if self.strategy == "DUMMY_RISE_FALL":
            return self._dummy_rise_fall()
        if self.strategy == "ACCU":
            return self._accumulator_signal()
        elif self.strategy in ["CALL", "PUT"]:
            return self._rise_fall_signal()
        elif self.strategy in ["MULTUP", "MULTDOWN"]:
            return self._multiplier_signal()
        elif self.strategy in ["ONETOUCH", "NOTOUCH"]:
            return self._touch_signal()
        elif self.strategy in ["DIGITOVER", "DIGITUNDER"]:
            return self._digit_over_under_signal()
        elif self.strategy in ["HIGHER", "LOWER"]:
            return self._higher_lower_signal()
        elif self.strategy in ["DIGITEVEN", "DIGITODD"]:
            return self._even_odd_signal()
        elif self.strategy in ["DIGITMATCH", "DIGITDIFF"]:
            return self._match_differ_signal()
        return None

    def check_exit(self, contract: dict) -> Optional[str]:
        if self.strategy == "ACCU":
            bb = self.indicators.bbands(20, 2)
            macd = self.indicators.macd(12, 26, 9)
            price = self.indicators.prices[-1]
            if bb["middle"] and price > 0:
                # 1. Price too far from middle band
                dist = abs(price - bb["middle"]) / bb["middle"]
                if dist > 0.20:
                    return "Price moved >15% from middle band"

                # 2. MACD histogram (green/red bars) spike
                if abs(macd["histogram"]) > 0.10:
                    return "MACD histogram spike beyond ±0.10"

                # 3. MACD signal line (red line) extreme
                if abs(macd["signal"]) > 0.10:
                    return "MACD signal line beyond ±0.10"

                # 4. Price near Bollinger Band edge
                band_width = bb["upper"] - bb["lower"]
                if band_width > 0:
                    dist_to_upper = bb["upper"] - price
                    dist_to_lower = price - bb["lower"]
                    if dist_to_upper < band_width * 0.15:
                        return f"Price near upper band ({dist_to_upper:.3f} from edge)"
                    if dist_to_lower < band_width * 0.15:
                        return f"Price near lower band ({dist_to_lower:.3f} from edge)"
            return None
        elif self.strategy == "DUMMY_RISE_FALL":
            entry_epoch = contract.get("entry_epoch", 0)
            current_epoch = self.indicators.ticks[-1].get("epoch", 0) if self.indicators.ticks else 0
            if current_epoch - entry_epoch > 10:
                return "dummy_time_exit"
            return None
        return None

    def _dummy_rise_fall(self) -> Optional[Dict[str, Any]]:
        if self.tick_count % 5 != 0:
            return None
        self.last_direction = "PUT" if self.last_direction == "CALL" else "CALL"
        return {
            "action": "buy",
            "contract_type": self.last_direction,
            "duration": 5,
            "duration_unit": "t",
            "reason": "Dummy test signal"
        }

    def _accumulator_signal(self) -> Optional[Dict[str, Any]]:
        bb = self.indicators.bbands(20, 2)
        if not bb["middle"]:
            return None
        price = self.indicators.prices[-1]
        dist_from_middle = abs(price - bb["middle"]) / bb["middle"]
        if dist_from_middle < 0.10:
            return {
                "action": "buy",
                "contract_type": "ACCU",
                "growth_rate": 0.01,
                "reason": f"Price near middle band ({dist_from_middle:.3%})"
            }
        return None

    def _rise_fall_signal(self) -> Optional[Dict[str, Any]]:
        if len(self.indicators.prices) < 21:
            return None
        ema8 = self.indicators.ema(8)
        ema21 = self.indicators.ema(21)
        rsi = self.indicators.rsi(14)
        if ema8 > ema21 and 50 < rsi < 70:
            return {"action": "buy", "contract_type": "CALL", "duration": 5, "duration_unit": "t", "reason": "EMA8>EMA21, RSI>50"}
        elif ema8 < ema21 and 30 < rsi < 50:
            return {"action": "buy", "contract_type": "PUT", "duration": 5, "duration_unit": "t", "reason": "EMA8<<EMA21, RSI<<50"}
        return None

    def _multiplier_signal(self) -> Optional[Dict[str, Any]]:
        sig = self._rise_fall_signal()
        if sig:
            sig["contract_type"] = "MULTUP" if sig["contract_type"] == "CALL" else "MULTDOWN"
            sig["multiplier"] = 100
            sig["stop_loss"] = 5.0
            return sig
        return None

    def _touch_signal(self) -> Optional[Dict[str, Any]]:
        bb = self.indicators.bbands(20, 2)
        price = self.indicators.prices[-1]
        if not bb["upper"]:
            return None
        if price < bb["lower"] * 1.001:
            return {"action": "buy", "contract_type": "ONETOUCH", "barrier": "+0.500", "duration": 5, "duration_unit": "m"}
        elif price > bb["upper"] * 0.999:
            return {"action": "buy", "contract_type": "NOTOUCH", "barrier": "+0.500", "duration": 5, "duration_unit": "m"}
        return None

    def _digit_over_under_signal(self) -> Optional[Dict[str, Any]]:
        if not self.indicators.ticks:
            return None
        rsi = self.indicators.rsi(14)
        if rsi > 60:
            return {"action": "buy", "contract_type": "DIGITOVER", "barrier": "5", "duration": 1, "duration_unit": "t"}
        elif rsi < 40:
            return {"action": "buy", "contract_type": "DIGITUNDER", "barrier": "4", "duration": 1, "duration_unit": "t"}
        return None

    def _higher_lower_signal(self) -> Optional[Dict[str, Any]]:
        if len(self.indicators.prices) < 21:
            return None
        ema8 = self.indicators.ema(8)
        ema21 = self.indicators.ema(21)
        if ema8 > ema21:
            return {"action": "buy", "contract_type": "HIGHER", "barrier": "+0.438", "duration": 5, "duration_unit": "t"}
        else:
            return {"action": "buy", "contract_type": "LOWER", "barrier": "-0.438", "duration": 5, "duration_unit": "t"}

    def _even_odd_signal(self) -> Optional[Dict[str, Any]]:
        if not self.indicators.ticks or len(self.indicators.ticks) < 10:
            return None
        recent_digits = [int(str(t["quote"])[-1]) for t in self.indicators.ticks[-10:]]
        even_count = sum(1 for d in recent_digits if d % 2 == 0)
        if even_count > 6:
            return {"action": "buy", "contract_type": "DIGITEVEN", "duration": 1, "duration_unit": "t"}
        elif even_count < 4:
            return {"action": "buy", "contract_type": "DIGITODD", "duration": 1, "duration_unit": "t"}
        return None

    def _match_differ_signal(self) -> Optional[Dict[str, Any]]:
        if not self.indicators.ticks or len(self.indicators.ticks) < 2:
            return None
        last_digit = int(str(self.indicators.ticks[-1]["quote"])[-1])
        prev_digit = int(str(self.indicators.ticks[-2]["quote"])[-1])
        if last_digit == prev_digit:
            return {"action": "buy", "contract_type": "DIGITMATCH", "barrier": str(last_digit), "duration": 1, "duration_unit": "t"}
        else:
            return {"action": "buy", "contract_type": "DIGITDIFF", "barrier": str(last_digit), "duration": 1, "duration_unit": "t"}