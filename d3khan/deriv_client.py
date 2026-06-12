import asyncio
from typing import Dict, Callable, Optional, Any
from deriv_api import DerivAPI

class DerivClient:
    def __init__(self, token: str, app_id: int, ws_url: str):
        self.token = token
        self.app_id = app_id
        self.ws_url = ws_url
        self.api: Optional[DerivAPI] = None
        self.authorized = False
        self.balance = 0.0
        self.currency = "USD"
        
        self.callbacks: Dict[str, Callable] = {
            "tick": lambda x: None,
            "candles": lambda x: None,
            "ohlc": lambda x: None,
            "balance": lambda x: None,
            "buy": lambda x: None,
            "contract_update": lambda x: None,
        }
        self._disposables = []

    async def _test_tcp(self):
        """Test if we can reach Deriv's server at all."""
        try:
            import ssl
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('ws.derivws.com', 443, 
ssl=ssl.create_default_context()),
                timeout=5
            )
            writer.close()
            await writer.wait_closed()
            print("[Deriv] TCP connection to ws.derivws.com:443 OK")
            return True
        except Exception as e:
            print(f"[Deriv] TCP connection FAILED: {e}")
            return False

    async def connect(self):
        print(f"[Deriv] Starting connection. Token prefix: {self.token[:6]}...")
        
        tcp_ok = await self._test_tcp()
        if not tcp_ok:
            print("[Deriv] Network appears to block Deriv. Will use demo mode.")
            return False

        try:
            print("[Deriv] Creating DerivAPI with default endpoint...")
            self.api = DerivAPI(app_id=self.app_id)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[Deriv] Default endpoint failed: {e}")
            try:
                print(f"[Deriv] Trying explicit endpoint: {self.ws_url}")
                self.api = DerivAPI(endpoint=self.ws_url, app_id=self.app_id)
                await asyncio.sleep(2)
            except Exception as e2:
                print(f"[Deriv] Explicit endpoint failed: {e2}")
                return False
        
        print("[Deriv] Sending authorize...")
        try:
            auth = await asyncio.wait_for(self.api.authorize(self.token), 
timeout=60)
        except asyncio.TimeoutError:
            print("[Deriv] Authorize timed out after 60s")
            return False
        except Exception as e:
            print(f"[Deriv] Authorize error: {e}")
            return False
        
        if auth and not auth.get("error"):
            self.authorized = True
            auth_data = auth.get("authorize", {})
            self.balance = float(auth_data.get("balance", 0))
            self.currency = auth_data.get("currency", "USD")
            print(f"[Deriv] SUCCESS! Balance: {self.balance} {self.currency}")
            await self._safe_callback("balance", self.balance)
            await self._subscribe_balance()
            return True
        else:
            error = auth.get("error", {}) if auth else "Unknown auth error"
            print(f"[Deriv] Auth rejected: {error}")
            return False

    async def _safe_callback(self, key: str, data: Any):
        try:
            await self.callbacks[key](data)
        except Exception as e:
            print(f"[Deriv] Callback error ({key}): {e}")

    async def _subscribe_balance(self):
        try:
            print("[Deriv] Subscribing to balance updates...")
            source = await self.api.subscribe({"balance": 1, "subscribe": 1})
            disp = source.subscribe(lambda msg: 
asyncio.create_task(self._on_balance_msg(msg)))
            self._disposables.append(disp)
            print("[Deriv] Balance subscription active")
        except Exception as e:
            print(f"[Deriv] Balance subscribe error: {e}")

    async def _on_balance_msg(self, msg: dict):
        bal_data = msg.get("balance", {})
        if bal_data:
            balance = float(bal_data.get("balance", 0))
            self.balance = balance
            print(f"[Deriv] Balance update: {balance}")
            await self._safe_callback("balance", balance)

    async def subscribe_ticks(self, symbol: str):
        try:
            print(f"[Deriv] Subscribing to ticks: {symbol}")
            source = await self.api.subscribe({"ticks": symbol, "subscribe": 1})
            disp = source.subscribe(lambda msg: 
asyncio.create_task(self._on_tick_msg(msg)))
            self._disposables.append(disp)
            print(f"[Deriv] Ticks active: {symbol}")
        except Exception as e:
            print(f"[Deriv] Tick subscribe error: {e}")

    async def _on_tick_msg(self, msg: dict):
        tick = msg.get("tick", {})
        if tick:
            await self._safe_callback("tick", tick)

    async def subscribe_candles(self, symbol: str, granularity: int):
        try:
            print(f"[Deriv] Subscribing to candles: {symbol} {granularity}s")
            req = {
                "ticks_history": symbol,
                "end": "latest",
                "style": "candles",
                "granularity": granularity,
                "count": 1000,
                "subscribe": 1
            }
            source = await self.api.subscribe(req)
            disp = source.subscribe(lambda msg: 
asyncio.create_task(self._on_candle_msg(msg)))
            self._disposables.append(disp)
            print(f"[Deriv] Candles active: {symbol} {granularity}s")
        except Exception as e:
            print(f"[Deriv] Candle subscribe error: {e}")

    async def _on_candle_msg(self, msg: dict):
        msg_type = msg.get("msg_type")
        if msg_type == "candles":
            await self._safe_callback("candles", msg)
        elif msg_type == "ohlc":
            await self._safe_callback("ohlc", msg)

    async def get_tick_history(self, symbol: str, count: int = 1000):
        """One-shot request for historical ticks."""
        try:
            req = {
                "ticks_history": symbol,
                "end": "latest",
                "style": "ticks",
                "count": count
            }
            return await asyncio.wait_for(self.api.send(req), timeout=30)
        except Exception as e:
            return {"error": str(e)}

    async def subscribe_contract_updates(self, contract_id: str):
        try:
            req = {
                "proposal_open_contract": 1,
                "contract_id": contract_id,
                "subscribe": 1
            }
            source = await self.api.subscribe(req)
            disp = source.subscribe(lambda msg: 
asyncio.create_task(self._on_contract_msg(msg)))
            self._disposables.append(disp)
        except Exception as e:
            print(f"[Deriv] Contract subscribe error: {e}")

    async def _on_contract_msg(self, msg: dict):
        poc = msg.get("proposal_open_contract", {})
        if poc:
            await self._safe_callback("contract_update", poc)

    # --- THE FIXED METHODS USING DIRECT api.send() ---
    async def get_proposal(self, proposal_req: dict):
        """Bypasses api.proposal wrapper to avoid dictionary type-check errors."""
        return await asyncio.wait_for(self.api.send(proposal_req), timeout=10)

    async def buy_contract(self, proposal_id: str, price: float):
        """
        Buy a contract using a proposal ID and price.
        Bypasses api.buy wrapper to avoid strictly typed dictionary execution errors.
        """
        buy_request = {
            "buy": str(proposal_id),
            "price": float(price)
        }
        print(f"[Deriv] Sending buy request: {buy_request}")
        try:
            result = await asyncio.wait_for(self.api.send(buy_request), timeout=10)
            return result
        except Exception as e:
            print(f"[Deriv] Buy contract error: {type(e).__name__}: {e}")
            raise

    async def sell_contract(self, contract_id: str, price: float = 0.0):
        """
        Sells an open contract using its ID. 
        Accepts the price argument passed down from engine.py to prevent TypeError.
        """
        sell_request = {
            "sell": str(contract_id),
            "price": float(price)
        }
        print(f"[Deriv] Sending sell request: {sell_request}")
        return await asyncio.wait_for(self.api.send(sell_request), timeout=10)
    # ---------------------------------

    async def close(self):
        for disp in self._disposables:
            try:
                if hasattr(disp, 'dispose'):
                    disp.dispose()
            except:
                pass
        self._disposables.clear()
        if self.api:
            try:
                if hasattr(self.api, 'disconnect'):
                    await self.api.disconnect()
            except:
                pass