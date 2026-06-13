import asyncio
import random
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import *
from database import Database
from deriv_client import DerivClient
from strategies import StrategyEngine
from models import *

DERIV_SYMBOL = "1HZ10V"

# ─── Session Cache (temporary JSON file, NOT the database) ───
import json as _json
import os as _os

CACHE_FILE = "d3khan_session_cache.json"

class SessionCache:
    """Lightweight JSON cache for current-session stats. Deleted by user without touching the DB."""
    def __init__(self, filepath: str = CACHE_FILE):
        self.filepath = filepath
        self._data = self._load()

    def _load(self) -> dict:
        if _os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return _json.load(f)
            except Exception:
                pass
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "profit": 0.0,
            "win_rate": 0.0,
            "consecutive_losses": 0,
            "session_id": None,
        }

    def _save(self):
        with open(self.filepath, "w") as f:
            _json.dump(self._data, f)

    def record_trade(self, profit: float, session_id: int):
        self._data["total_trades"] += 1
        self._data["profit"] = round(self._data["profit"] + profit, 2)
        if profit > 0:
            self._data["wins"] += 1
            self._data["consecutive_losses"] = 0
        else:
            self._data["losses"] += 1
            self._data["consecutive_losses"] += 1
        total = self._data["total_trades"]
        self._data["win_rate"] = round((self._data["wins"] / total * 100), 2) if total > 0 else 0.0
        self._data["session_id"] = session_id
        self._save()

    def get_stats(self) -> dict:
        return dict(self._data)

    def reset(self, session_id: int):
        self._data = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "profit": 0.0,
            "win_rate": 0.0,
            "consecutive_losses": 0,
            "session_id": session_id,
        }
        self._save()

    def clear(self):
        if _os.path.exists(self.filepath):
            try:
                _os.remove(self.filepath)
            except Exception:
                pass
        self._data = {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "profit": 0.0,
            "win_rate": 0.0,
            "consecutive_losses": 0,
            "session_id": None,
        }

    @property
    def file_size(self) -> int:
        if _os.path.exists(self.filepath):
            return _os.path.getsize(self.filepath)
        return 0


class TradingEngine:
    def __init__(self):
        self.db = Database()
        self.deriv = DerivClient(TOKEN, APP_ID, DERIV_WS_URL)
        self.strategy_engine = StrategyEngine("DUMMY_RISE_FALL")
        self.state = EngineState()
        self.state.current_session = None
        self.frontend_clients: List = []
        self.is_trading_enabled = False
        self.consecutive_losses = 0
        self.session_profit = 0.0
        self.open_contracts: Dict[str, Any] = {}
        self._demo_mode = False
        self._demo_task = None
        self.session_cache = SessionCache()
        self._background_tasks = set()

        self.ticks: List[dict] = []
        self.candles_1m: List[dict] = []
        self.candles_5m: List[dict] = []
        self.max_ticks = 5000
        self.max_candles = 2000

        # Dynamic options (updated from frontend in real-time)
        self.stake = float(STAKE)
        self.max_loss = float(MAX_DAILY_LOSS)
        self.max_consec = int(MAX_CONSECUTIVE_LOSSES)
        self.tp_target = float(TAKE_PROFIT)

    def _create_task(self, coro):
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def _get_stake(self, contract_type: str = "") -> float:
        """Return stake clamped between MIN_STAKE and MAX_STAKE."""
        return max(float(MIN_STAKE), min(float(self.stake), float(MAX_STAKE)))

    async def _demo_tick_loop(self):
        base_price = 5000.0
        while True:
            await asyncio.sleep(1)
            noise = (random.random() - 0.5) * 2.0
            base_price += noise
            tick = {
                "epoch": int(datetime.now().timestamp()),
                "quote": round(base_price, 3),
                "symbol": SYMBOL
            }
            await self._on_tick(tick)

    def _generate_demo_history(self):
        now = int(datetime.now().timestamp())
        base_price = 5000.0
        for i in range(21600, 0, -1):
            epoch = now - i
            noise = (random.random() - 0.5) * 0.2
            base_price += noise
            tick = {
                "epoch": epoch,
                "quote": round(base_price, 3),
                "symbol": SYMBOL
            }
            self.ticks.append({"epoch": tick["epoch"], "price": tick["quote"]})
            self._update_candles_from_tick(tick)
            if len(self.ticks) > self.max_ticks:
                self.ticks = self.ticks[-self.max_ticks:]

    async def start(self):
        await self.db.connect()

        self.deriv.callbacks["tick"] = self._on_tick
        self.deriv.callbacks["candles"] = self._on_candles_history
        self.deriv.callbacks["ohlc"] = self._on_ohlc
        self.deriv.callbacks["balance"] = self._on_balance
        self.deriv.callbacks["contract_update"] = self._on_contract_update

        deriv_connected = False
        try:
            print("[Engine] Attempting Deriv connection...")
            deriv_connected = await self.deriv.connect()
            if deriv_connected:
                self._demo_mode = False
                self.state.balance = self.deriv.balance
                print(f"[Engine] REAL MODE: Balance = ${self.state.balance:.2f}")
                await self.deriv.subscribe_ticks(DERIV_SYMBOL)
                await self.deriv.subscribe_candles(DERIV_SYMBOL, 60)
                await self.deriv.subscribe_candles(DERIV_SYMBOL, 300)
                await self._load_tick_history()
                await self._log("info", f"Deriv connected. Real balance: ${self.state.balance:.2f}")
            else:
                raise Exception("Deriv auth returned False")
        except Exception as e:
            print(f"[Engine] Deriv connection failed: {e}")
            await self._log("warning", f"Deriv connection failed: {e} — starting DEMO mode")
            self._demo_mode = True
            self.state.balance = CAPITAL
            self._generate_demo_history()
            self._demo_task = asyncio.create_task(self._demo_tick_loop())
            print(f"[Engine] DEMO MODE: Balance = ${self.state.balance:.2f}")

        await self._start_session()
        self.session_cache.reset(self.state.current_session.id)
        self.state.is_running = True

        await self._broadcast({
            "type": "engine_status",
            "status": "running",
            "demo_mode": self._demo_mode
        })

        await self._broadcast({
            "type": "init",
            "state": {
                "balance": self.state.balance,
                "session_pl": self.session_profit,
                "total_trades": 0,
                "total_wins": 0,
                "total_losses": 0,
                "open_contracts": [],
                "is_running": True,
                "is_trading_enabled": False,
                "current_session": {
                    "id": self.state.current_session.id if self.state.current_session else None,
                    "profit": 0,
                    "initial_balance": self.state.balance
                }
            },
            "version": VERSION,
            "build": BUILD_NUMBER,
            "demo_mode": self._demo_mode,
            "ticks": self.ticks[-2000:],
            "candles_1m": self.candles_1m,
            "candles_5m": self.candles_5m
        })

        await self._broadcast({
            "type": "balance",
            "balance": self.state.balance,
            "session_pl": self.session_profit
        })

    async def shutdown(self):
        """Clean shutdown: cancel all tasks, close connections."""
        print("[Engine] Shutdown initiated...")
        for task in list(self._background_tasks):
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

        if self._demo_task:
            self._demo_task.cancel()
            try:
                await self._demo_task
            except asyncio.CancelledError:
                pass

        try:
            await self.deriv.close()
        except Exception as e:
            print(f"[Engine] Deriv close error: {e}")

        if self.db._conn:
            try:
                await self.db._conn.close()
            except Exception as e:
                print(f"[Engine] DB close error: {e}")
        print("[Engine] Shutdown complete.")

    async def _load_tick_history(self):
        try:
            resp = await self.deriv.get_tick_history(DERIV_SYMBOL, 1000)
            if resp and not resp.get("error") and resp.get("history"):
                times = resp["history"].get("times", [])
                prices = resp["history"].get("prices", [])
                self.ticks = [
                    {"epoch": int(times[i]), "price": float(prices[i])}
                    for i in range(len(times))
                ]
                print(f"[Engine] Loaded {len(self.ticks)} historical ticks")
        except Exception as e:
            print(f"[Engine] Tick history load failed: {e}")

    async def _start_session(self):
        session = Session(initial_balance=self.state.balance or CAPITAL)
        cursor = await self.db.execute(
            "INSERT INTO sessions (initial_balance, status) VALUES (?, ?)",
            (session.initial_balance, "active")
        )
        await self.db.commit()
        session.id = cursor.lastrowid
        self.state.current_session = session
        self.session_profit = 0.0
        self.consecutive_losses = 0

    async def _on_balance(self, balance: float):
        self.state.balance = balance
        print(f"[Engine] Balance updated: ${balance:.2f}")
        await self._broadcast({
            "type": "balance",
            "balance": balance,
            "session_pl": self.session_profit
        })

    async def _on_tick(self, tick: dict):
        self.state.last_tick = tick
        self.strategy_engine.update(tick)

        self.ticks.append({
            "epoch": tick.get("epoch", 0),
            "price": tick.get("quote", 0)
        })
        if len(self.ticks) > self.max_ticks:
            self.ticks.pop(0)

        if self._demo_mode:
            self._update_candles_from_tick(tick)

        price = tick.get("quote", 0)
        barrier_upper = round(price + 0.438, 3)
        barrier_lower = round(price - 0.438, 3)

        await self._broadcast({
            "type": "tick",
            "tick": tick,
            "barriers": {
                "upper": barrier_upper,
                "lower": barrier_lower,
                "active": True
            }
        })

        for contract_id, contract in list(self.open_contracts.items()):
            exit_reason = self.strategy_engine.check_exit(contract)
            if exit_reason:
                await self._sell_contract(contract_id, exit_reason)

        if self.is_trading_enabled and len(self.open_contracts) < 3:
            signal = self.strategy_engine.get_signal()
            if signal:
                await self._log("info", f"Signal fired: {signal.get('contract_type')} — {signal.get('reason', 'no reason')}")
                if self._demo_mode:
                    await self._execute_demo_trade(signal)
                else:
                    await self._execute_signal(signal)

    def _update_candles_from_tick(self, tick: dict):
        epoch = tick.get("epoch", 0)
        price = tick.get("quote", 0)
        for granularity, target in [(60, self.candles_1m), (300, self.candles_5m)]:
            bucket = (epoch // granularity) * granularity
            if target and len(target) > 0 and target[-1].get("epoch") == bucket:
                c = target[-1]
                if price > c["high"]: c["high"] = price
                if price < c["low"]: c["low"] = price
                c["close"] = price
            else:
                target.append({
                    "epoch": bucket,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price
                })
            if len(target) > self.max_candles:
                target.pop(0)

    async def _on_candles_history(self, msg: dict):
        candles = msg.get("candles", [])
        granularity = msg.get("echo_req", {}).get("granularity", 60)
        if not candles:
            return
        parsed = [
            {"epoch": c["epoch"], "open": float(c["open"]), "high": float(c["high"]),
             "low": float(c["low"]), "close": float(c["close"])}
            for c in candles
        ]
        if granularity == 300:
            self.candles_5m = parsed
        else:
            self.candles_1m = parsed
        print(f"[Engine] Loaded {len(parsed)} candles for {granularity}s")
        await self._broadcast({
            "type": "candles_history",
            "candles": parsed,
            "granularity": granularity
        })

    async def _on_ohlc(self, msg: dict):
        ohlc = msg.get("ohlc", {})
        if not ohlc:
            return
        granularity = ohlc.get("granularity", 60)
        open_time = ohlc.get("open_time")
        if not open_time:
            return
        candle = {
            "epoch": open_time,
            "open": float(ohlc.get("open", 0)),
            "high": float(ohlc.get("high", 0)),
            "low": float(ohlc.get("low", 0)),
            "close": float(ohlc.get("close", 0)),
        }
        target = self.candles_5m if granularity == 300 else self.candles_1m
        if target and len(target) > 0 and target[-1].get("epoch") == open_time:
            target[-1] = candle
        else:
            target.append(candle)
        if len(target) > self.max_candles:
            target.pop(0)
        await self._broadcast({
            "type": "ohlc",
            "ohlc": ohlc,
            "granularity": granularity
        })

    async def _execute_demo_trade(self, signal: dict):
        amount = self._get_stake(signal.get("contract_type", ""))
        if self.state.balance < amount:
            await self._log("warning", "Insufficient balance for trade")
            return
        if self.session_profit <= -self.max_loss:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max daily loss reached"})
            return
        if self.consecutive_losses >= self.max_consec:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max consecutive losses reached"})
            return
        if self.session_profit >= self.tp_target:
            self.is_trading_enabled = False
            await self._broadcast({"type": "info", "message": "Take profit target reached"})
            return

        self.state.balance -= amount
        await self._broadcast({
            "type": "balance",
            "balance": self.state.balance,
            "session_pl": self.session_profit
        })

        contract_id = f"DEMO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}"
        entry_price = self.state.last_tick["quote"] if self.state.last_tick else 5000.0
        buy_data = {
            "contract_id": contract_id,
            "symbol": SYMBOL,
            "contract_type": signal["contract_type"],
            "stake": amount,
            "entry_price": entry_price,
            "entry_epoch": int(datetime.now().timestamp()),
            "status": "open",
            "barrier_upper": round(entry_price + 0.438, 3),
            "barrier_lower": round(entry_price - 0.438, 3),
            "max_profit": 0,
            "take_profit": signal.get("take_profit", 0)
        }
        self.open_contracts[contract_id] = buy_data

        await self.db.execute(
            "INSERT INTO trades (session_id, contract_id, symbol, contract_type, strategy, stake, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.state.current_session.id, contract_id, SYMBOL, signal["contract_type"], self.strategy_engine.strategy, amount, "open")
        )
        await self.db.commit()
        await self._broadcast({"type": "trade_opened", "contract": buy_data})
        await self._log("info", f"DEMO trade opened: {signal['contract_type']} @ ${amount} | Balance: ${self.state.balance:.2f}")

        self._create_task(self._demo_close_contract(contract_id, signal.get("take_profit", 0)))

    async def _demo_close_contract(self, contract_id: str, take_profit: float = 0):
        """Close demo contract when TP is hit or after random delay."""
        tp = float(take_profit)
        while True:
            await asyncio.sleep(1)
            if contract_id not in self.open_contracts:
                return
            contract = self.open_contracts[contract_id]
            stake = contract.get("stake", self.stake)
            elapsed = int(datetime.now().timestamp()) - contract.get("entry_epoch", 0)
            simulated_profit = round((elapsed * 0.02) + (random.random() - 0.3) * 0.1, 2)
            if simulated_profit > stake * 0.95:
                simulated_profit = round(stake * 0.95, 2)
            contract["profit"] = simulated_profit
            if tp > 0 and simulated_profit >= tp:
                await self._close_trade(contract_id, simulated_profit, "won")
                await self._log("info", f"DEMO TP hit: ${simulated_profit:.2f}")
                return
            if elapsed > 15:
                is_win = simulated_profit > 0
                profit = round(simulated_profit, 2) if is_win else round(-stake, 2)
                status = "won" if is_win else "lost"
                await self._close_trade(contract_id, profit, status)
                return

    async def _on_buy(self, buy_data: dict):
        contract_id = buy_data.get("contract_id")
        if contract_id:
            entry_price = buy_data.get("entry_tick", buy_data.get("entry_price", 0))
            if not entry_price and self.state.last_tick:
                entry_price = self.state.last_tick.get("quote", 0)
            buy_data["entry_price"] = entry_price
            buy_data["barrier_upper"] = round(entry_price + 0.438, 3) if entry_price else 0
            buy_data["barrier_lower"] = round(entry_price - 0.438, 3) if entry_price else 0
            buy_data["max_profit"] = 0
            self.open_contracts[contract_id] = buy_data
            await self.deriv.subscribe_contract_updates(contract_id)
            ct = buy_data.get("contract_type") or self.strategy_engine.strategy
            await self.db.execute(
                "INSERT INTO trades (session_id, contract_id, symbol, contract_type, strategy, stake, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.state.current_session.id, contract_id, SYMBOL, ct, self.strategy_engine.strategy, self.stake, "open")
            )
            await self.db.commit()
            await self._broadcast({"type": "trade_opened", "contract": buy_data})
            await self._log("info", f"Real trade opened: {ct} @ ${self.stake} | ID: {contract_id}")

    async def _on_contract_update(self, contract: dict):
        contract_id = contract.get("contract_id")
        if contract_id not in self.open_contracts:
            return

        old = self.open_contracts[contract_id]
        contract["sell_blocked"] = old.get("sell_blocked", False)
        contract["sell_pending"] = old.get("sell_pending", False)
        contract["entry_price"] = old.get("entry_price", contract.get("entry_tick", 0))
        contract["barrier_upper"] = old.get("barrier_upper", 0)
        contract["barrier_lower"] = old.get("barrier_lower", 0)
        contract["max_profit"] = max(old.get("max_profit", 0), float(contract.get("profit", 0)))
        contract["take_profit"] = old.get("take_profit", 0)
        self.open_contracts[contract_id] = contract

        # Broadcast FIRST so stats page sees the profit update immediately
        await self._broadcast({"type": "contract_update", "contract": contract})

        # TP check: close immediately if profit >= target (no loops, no blocking)
        current_profit = float(contract.get("profit", 0))
        tp = float(old.get("take_profit", 0))
        if tp > 0 and current_profit >= tp:
            await self._close_trade(contract_id, current_profit, "won")
            return

        status = contract.get("status")
        if status in ("sold", "won", "lost"):
            profit = float(contract.get("profit", 0))
            await self._close_trade(contract_id, profit, status)
            return

    async def _execute_signal(self, signal: dict):
        if not self.deriv.authorized:
            await self._log("error", "Cannot trade — Deriv not connected")
            return
        if self.state.balance <= 0:
            return
        if self.session_profit <= -self.max_loss:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max daily loss reached"})
            return
        if self.consecutive_losses >= self.max_consec:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max consecutive losses reached"})
            return
        if self.session_profit >= self.tp_target:
            self.is_trading_enabled = False
            await self._broadcast({"type": "info", "message": "Take profit target reached"})
            return

        if not signal or not signal.get("contract_type"):
            await self._log("error", "Invalid signal: missing contract_type")
            return

        amount = self._get_stake(signal.get("contract_type", ""))

        proposal_req = {
            "proposal": 1,
            "amount": amount,
            "basis": "stake",
            "contract_type": signal["contract_type"],
            "currency": "USD",
            "symbol": DERIV_SYMBOL,
        }

        if "duration" in signal:
            proposal_req["duration"] = signal["duration"]
            proposal_req["duration_unit"] = signal.get("duration_unit", "t")

        if "barrier" in signal:
            proposal_req["barrier"] = signal["barrier"]

        if signal.get("contract_type") == "ACCU":
            proposal_req["growth_rate"] = float(GROWTH_RATE)

        if "multiplier" in signal:
            proposal_req["multiplier"] = signal["multiplier"]
            stop_pct = signal.get("stop_loss", MULTIPLIER_TRAILING_STOP)
            stop_usd = amount * signal["multiplier"] * float(stop_pct) / 100
            proposal_req["stop_loss"] = round(stop_usd, 2)
            proposal_req["stop_type"] = "trailing"

        try:
            response = await self.deriv.get_proposal(proposal_req)
            if not response:
                await self._log("error", "Proposal returned empty response")
                return
            if "error" in response:
                err = response.get("error", {})
                err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                await self._log("error", f"Proposal failed: {err_msg}")
                return
            proposal = response.get("proposal", {})
            proposal_id = proposal.get("id")
            price = proposal.get("ask_price")
            if not proposal_id or not price:
                await self._log("error", "Invalid proposal response")
                return
            buy_response = await self.deriv.buy_contract(str(proposal_id), float(price))
            if not buy_response:
                await self._log("error", "Buy returned empty response")
                return
            if "error" in buy_response:
                err = buy_response.get("error", {})
                err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                await self._log("error", f"Buy failed: {err_msg}")
                return
            buy_data = buy_response.get("buy", {})
            buy_data["take_profit"] = signal.get("take_profit", 0)
            await self._on_buy(buy_data)
        except Exception as e:
            err_str = str(e) if str(e) else type(e).__name__
            await self._log("error", f"Trade execution error: {err_str}")

    async def _sell_contract(self, contract_id: str, reason: str):
        contract = self.open_contracts.get(contract_id)
        if not contract:
            return
        if contract.get("sell_blocked"):
            return
        if contract.get("sell_pending"):
            return
        contract["sell_pending"] = True

        if self._demo_mode:
            if contract_id in self.open_contracts:
                is_win = random.random() > 0.5
                stake = contract.get("stake", self.stake)
                profit = round(stake * 0.95, 2) if is_win else round(-stake, 2)
                status = "won" if is_win else "lost"
                await self._close_trade(contract_id, profit, status)
                await self._log("info", f"DEMO sell: {reason}")
            return

        try:
            price = self.state.last_tick["quote"] if self.state.last_tick else 0
            await self.deriv.sell_contract(contract_id, price)
            await self._log("info", f"Sell signal: {reason}")
        except Exception as e:
            err_str = str(e) if str(e) else type(e).__name__
            if "not offered" in err_str.lower() or "couldn't process" in err_str.lower() or "sell_blocked" in err_str.lower():
                contract["sell_blocked"] = True
                await self._log("warning", f"Sell blocked for {contract_id}: resale not offered. Contract will expire naturally.")
            else:
                await self._log("error", f"Sell failed: {err_str}")
            contract["sell_pending"] = False

    async def _close_trade(self, contract_id: str, profit: float, status: str):
        if contract_id not in self.open_contracts:
            return
        contract = self.open_contracts[contract_id]
        stake = contract.get("stake", self.stake)
        del self.open_contracts[contract_id]

        await self.db.execute(
            "UPDATE trades SET profit = ?, status = ?, closed_at = CURRENT_TIMESTAMP WHERE contract_id = ?",
            (profit, status, contract_id)
        )
        await self.db.commit()

        self.session_profit += profit
        self.state.current_session.profit = self.session_profit
        self.state.current_session.total_trades += 1

        if profit > 0:
            self.state.current_session.wins += 1
            self.consecutive_losses = 0
            if self._demo_mode:
                self.state.balance += stake + profit
        else:
            self.state.current_session.losses += 1
            self.consecutive_losses += 1

        total = self.state.current_session.total_trades
        self.state.current_session.win_rate = (self.state.current_session.wins / total * 100) if total > 0 else 0

        self.session_cache.record_trade(profit, self.state.current_session.id)

        await self._broadcast({
            "type": "balance",
            "balance": self.state.balance,
            "session_pl": self.session_profit
        })

        await self._broadcast({
            "type": "trade_closed",
            "contract_id": contract_id,
            "profit": profit,
            "status": status,
            "session": self.state.current_session.dict()
        })

        await self._log("info", f"Trade closed: {status.upper()} | Profit: ${profit:.2f}")

        if self.consecutive_losses >= self.max_consec:
            self.is_trading_enabled = False
            await self._broadcast({"type": "auto_stop", "reason": "Max consecutive losses"})

    async def _log(self, level: str, message: str, source: str = "engine"):
        await self.db.execute(
            "INSERT INTO logs (level, message, source) VALUES (?, ?, ?)",
            (level, message, source)
        )
        await self.db.commit()
        await self._broadcast({
            "type": "log",
            "level": level,
            "message": message,
            "source": source,
            "timestamp": datetime.now().isoformat()
        })

    async def _broadcast(self, message: dict):
        dead = []
        for client in self.frontend_clients:
            try:
                await client.send_json(message)
            except:
                dead.append(client)
        for d in dead:
            if d in self.frontend_clients:
                self.frontend_clients.remove(d)

    async def set_trading_enabled(self, enabled: bool):
        self.is_trading_enabled = enabled
        self.state.is_trading_enabled = enabled
        await self._broadcast({"type": "trading_status", "enabled": enabled})
        await self._log("info", f"Trading {'enabled' if enabled else 'disabled'}")

    async def set_strategy(self, strategy: str):
        self.strategy_engine = StrategyEngine(strategy)
        await self._log("info", f"Strategy changed to {strategy}")

    async def set_options(self, options: dict):
        old_indicators = None
        old_tick_count = 0
        old_last_direction = "CALL"
        if self.strategy_engine:
            old_indicators = self.strategy_engine.indicators
            old_tick_count = self.strategy_engine.tick_count
            old_last_direction = self.strategy_engine.last_direction

        if "stake" in options:
            self.stake = max(float(MIN_STAKE), min(float(options["stake"]), float(MAX_STAKE)))
        if "max_loss" in options:
            self.max_loss = float(options["max_loss"])
        if "max_consec" in options:
            self.max_consec = int(options["max_consec"])
        if "tp_target" in options:
            self.tp_target = float(options["tp_target"])
        if "contract_type" in options:
            new_strategy = options["contract_type"]
            if self.strategy_engine.strategy != new_strategy:
                self.strategy_engine = StrategyEngine(new_strategy)
                if old_indicators:
                    self.strategy_engine.indicators = old_indicators
                    self.strategy_engine.tick_count = old_tick_count
                    self.strategy_engine.last_direction = old_last_direction
        await self._log("info", f"Options updated: stake=${self.stake}, max_loss=${self.max_loss}, max_consec={self.max_consec}, tp=${self.tp_target}, strategy={self.strategy_engine.strategy}")

    async def get_stats(self) -> dict:
        return self.session_cache.get_stats()

    async def clear_cache(self):
        self.session_cache.clear()
        self.session_profit = 0.0
        self.consecutive_losses = 0
        if self.state.current_session:
            self.state.current_session.total_trades = 0
            self.state.current_session.wins = 0
            self.state.current_session.losses = 0
            self.state.current_session.profit = 0
            self.state.current_session.win_rate = 0

        if self.state.current_session and self.state.current_session.id:
            await self.db.execute("DELETE FROM trades WHERE session_id=?", (self.state.current_session.id,))
            await self.db.execute("DELETE FROM logs")
            await self.db.execute(
                "UPDATE sessions SET total_trades=0, wins=0, losses=0, profit=0 WHERE id=?",
                (self.state.current_session.id,)
            )
            await self.db.commit()

        await self._log("info", "Cache cleared — temp file + DB logs/trades reset")
        await self._broadcast({
            "type": "cache_cleared",
            "state": {
                "balance": self.state.balance,
                "session_pl": 0.0,
                "total_trades": 0,
                "total_wins": 0,
                "total_losses": 0,
                "open_contracts": list(self.open_contracts.values()),
                "is_trading_enabled": self.is_trading_enabled,
            }
        })