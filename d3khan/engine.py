import asyncio
import random
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import *
from database import Database
from deriv_client import DerivClient
from strategies import StrategyEngine
from models import *

class TradingEngine:
    def __init__(self):
        self.db = Database()
        self.deriv = DerivClient(TOKEN, DERIV_WS_URL)
        self.strategy_engine = StrategyEngine("ACCU")
        self.state = EngineState()
        self.state.current_session = None
        self.frontend_clients: List = []
        self.is_trading_enabled = False
        self.consecutive_losses = 0
        self.session_profit = 0.0
        self.open_contracts: Dict[str, Any] = {}
        self._demo_mode = False
        self._demo_task = None

    async def start(self):
        await self.db.connect()

        # Try to connect to Deriv, but don't crash if it fails
        try:
            await self.deriv.connect()
            self.deriv.callbacks["balance"] = self._on_balance
            self.deriv.callbacks["tick"] = self._on_tick
            self.deriv.callbacks["candles"] = self._on_candles
            self.deriv.callbacks["buy"] = self._on_buy
            self.deriv.callbacks["contract_update"] = self._on_contract_update

            if self.deriv.authorized:
                await self.deriv.subscribe_ticks(SYMBOL)
                await self.deriv.subscribe_candles(SYMBOL, 60)
                await self.deriv.subscribe_candles(SYMBOL, 300)
                await self._log("info", "Connected to Deriv API")
            else:
                self._demo_mode = True
                await self._log("warning", "Deriv auth failed — running in DEMO mode with simulated ticks")
                self._demo_task = asyncio.create_task(self._demo_tick_loop())
        except Exception as e:
            self._demo_mode = True
            await self._log("warning", f"Deriv connection failed: {e} — running in DEMO mode")
            self._demo_task = asyncio.create_task(self._demo_tick_loop())

        await self._start_session()
        self.state.is_running = True
        await self._broadcast({"type": "engine_status", "status": "running", "demo_mode": self._demo_mode})

    async def _demo_tick_loop(self):
        """Simulate R_10 ticks for local testing without Deriv connection"""
        base_price = 5000.0
        while True:
            await asyncio.sleep(1)  # 1 second ticks
            noise = (random.random() - 0.5) * 2.0
            base_price += noise
            tick = {
                "epoch": int(datetime.now().timestamp()),
                "quote": round(base_price, 3),
                "symbol": SYMBOL
            }
            await self._on_tick(tick)

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
        await self._broadcast({
            "type": "balance",
            "balance": balance,
            "session_pl": self.session_profit
        })

    async def _on_tick(self, tick: dict):
        self.state.last_tick = tick
        self.strategy_engine.update(tick)
        await self._broadcast({"type": "tick", "tick": tick})

        for contract_id, contract in list(self.open_contracts.items()):
            exit_reason = self.strategy_engine.check_exit(contract)
            if exit_reason:
                await self._sell_contract(contract_id, exit_reason)

        if self.is_trading_enabled and len(self.open_contracts) < 3:
            signal = self.strategy_engine.get_signal()
            if signal:
                if self._demo_mode:
                    await self._execute_demo_trade(signal)
                else:
                    await self._execute_signal(signal)

    async def _on_candles(self, candles: dict):
        await self._broadcast({"type": "candles", "candles": candles})

    async def _execute_demo_trade(self, signal: dict):
        """Simulate a trade in demo mode without hitting Deriv"""
        if self.state.balance <= 0:
            return
        if self.session_profit <= -MAX_DAILY_LOSS:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max daily loss reached"})
            return
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max consecutive losses reached"})
            return
        if self.session_profit >= TAKE_PROFIT:
            self.is_trading_enabled = False
            await self._broadcast({"type": "info", "message": "Take profit target reached"})
            return

        contract_id = f"DEMO_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000,9999)}"
        buy_data = {
            "contract_id": contract_id,
            "symbol": SYMBOL,
            "contract_type": signal["contract_type"],
            "stake": STAKE,
            "entry_price": self.state.last_tick["quote"] if self.state.last_tick else 5000.0,
            "status": "open"
        }
        self.open_contracts[contract_id] = buy_data

        await self.db.execute(
            "INSERT INTO trades (session_id, contract_id, symbol, contract_type, strategy, stake, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (self.state.current_session.id, contract_id, SYMBOL, signal["contract_type"], self.strategy_engine.strategy, STAKE, "open")
        )
        await self.db.commit()
        await self._broadcast({"type": "trade_opened", "contract": buy_data})
        await self._log("info", f"DEMO trade opened: {signal['contract_type']} @ {STAKE} USD")

        # Simulate close after 5-15 seconds
        asyncio.create_task(self._demo_close_contract(contract_id))

    async def _demo_close_contract(self, contract_id: str):
        await asyncio.sleep(random.randint(5, 15))
        if contract_id not in self.open_contracts:
            return

        # 50/50 win/loss for demo
        is_win = random.random() > 0.5
        profit = round(STAKE * 0.95, 2) if is_win else round(-STAKE, 2)
        status = "won" if is_win else "lost"

        await self._close_trade(contract_id, profit, status)

    async def _on_buy(self, buy_data: dict):
        contract_id = buy_data.get("contract_id")
        if contract_id:
            self.open_contracts[contract_id] = buy_data
            await self.deriv.subscribe_contract_updates(contract_id)
            await self.db.execute(
                "INSERT INTO trades (session_id, contract_id, symbol, contract_type, strategy, stake, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.state.current_session.id, contract_id, SYMBOL, self.strategy_engine.strategy, self.strategy_engine.strategy, STAKE, "open")
            )
            await self.db.commit()
            await self._broadcast({"type": "trade_opened", "contract": buy_data})

    async def _on_contract_update(self, contract: dict):
        contract_id = contract.get("contract_id")
        if contract_id in self.open_contracts:
            self.open_contracts[contract_id] = contract
            status = contract.get("status")
            if status in ("sold", "won", "lost"):
                profit = contract.get("profit", 0)
                await self._close_trade(contract_id, profit, status)
            await self._broadcast({"type": "contract_update", "contract": contract})

    async def _execute_signal(self, signal: dict):
        if not self.deriv.authorized:
            await self._log("error", "Cannot trade — Deriv not connected")
            return
        if self.state.balance <= 0:
            return
        if self.session_profit <= -MAX_DAILY_LOSS:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max daily loss reached"})
            return
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.is_trading_enabled = False
            await self._broadcast({"type": "error", "message": "Max consecutive losses reached"})
            return
        if self.session_profit >= TAKE_PROFIT:
            self.is_trading_enabled = False
            await self._broadcast({"type": "info", "message": "Take profit target reached"})
            return

        proposal_req = {
            "proposal": 1,
            "amount": STAKE,
            "basis": "stake",
            "contract_type": signal["contract_type"],
            "currency": "USD",
            "symbol": SYMBOL
        }
        if "duration" in signal:
            proposal_req["duration"] = signal["duration"]
            proposal_req["duration_unit"] = signal["duration_unit"]
        if "barrier" in signal:
            proposal_req["barrier"] = signal["barrier"]
        if "growth_rate" in signal:
            proposal_req["growth_rate"] = signal["growth_rate"]
        if "multiplier" in signal:
            proposal_req["multiplier"] = signal["multiplier"]
            stop_usd = STAKE * signal["multiplier"] * MULTIPLIER_TRAILING_STOP / 100
            proposal_req["stop_loss"] = round(stop_usd, 2)
            proposal_req["stop_type"] = "trailing"

        try:
            response = await self.deriv.get_proposal(proposal_req)
            if "error" in response:
                await self._log("error", f"Proposal failed: {response['error']}")
                return
            proposal = response.get("proposal", {})
            proposal_id = proposal.get("id")
            price = proposal.get("ask_price")
            if not proposal_id or not price:
                await self._log("error", "Invalid proposal response")
                return
            buy_response = await self.deriv.buy_contract(proposal_id, price)
            if "error" in buy_response:
                await self._log("error", f"Buy failed: {buy_response['error']}")
                return
            await self._on_buy(buy_response.get("buy", {}))
        except Exception as e:
            await self._log("error", f"Trade execution error: {str(e)}")

    async def _sell_contract(self, contract_id: str, reason: str):
        if self._demo_mode:
            if contract_id in self.open_contracts:
                del self.open_contracts[contract_id]
            await self._log("info", f"DEMO sell: {reason}")
            return
        try:
            await self.deriv.sell_contract(contract_id)
            await self._log("info", f"Sell signal: {reason}")
        except Exception as e:
            await self._log("error", f"Sell failed: {str(e)}")

    async def _close_trade(self, contract_id: str, profit: float, status: str):
        if contract_id in self.open_contracts:
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
        else:
            self.state.current_session.losses += 1
            self.consecutive_losses += 1

        total = self.state.current_session.total_trades
        self.state.current_session.win_rate = (self.state.current_session.wins / total * 100) if total > 0 else 0

        await self._broadcast({
            "type": "trade_closed",
            "contract_id": contract_id,
            "profit": profit,
            "status": status,
            "session": self.state.current_session.dict()
        })

        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
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

    async def get_stats(self) -> dict:
        row = await self.db.fetchone(
            "SELECT COUNT(*) as total, SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins, SUM(CASE WHEN profit <= 0 THEN 1 ELSE 0 END) as losses, SUM(profit) as total_profit FROM trades WHERE session_id = ?",
            (self.state.current_session.id,)
        )
        return {
            "total_trades": row[0] or 0,
            "wins": row[1] or 0,
            "losses": row[2] or 0,
            "total_profit": row[3] or 0.0,
            "win_rate": (row[1] / row[0] * 100) if row[0] else 0
        }