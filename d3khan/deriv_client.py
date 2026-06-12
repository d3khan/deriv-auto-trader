import asyncio
from deriv_api import DerivAPI
from deriv_api.errors import APIError

class DerivClient:
    def __init__(self, token: str, app_id: int, url: str = None):
        self.token = token
        self.app_id = app_id
        self.url = url
        self.api = None
        self.authorized = False
        self.balance = 0.0
        self.callbacks = {}
        self.running = False
        self._sources = {}
        self._subs = {}
        self._heartbeat_task = None

    async def connect(self):
        try:
            self.api = DerivAPI(app_id=self.app_id)
            self.running = True
            self._heartbeat_task = asyncio.create_task(self._heartbeat())
            auth_response = await self.authorize()
            if "error" in auth_response:
                print(f"[Deriv] Auth failed: {auth_response['error']}")
                self.authorized = False
            else:
                self.authorized = True
                print(f"[Deriv] Connected and authorized. Balance: {self.balance}")
        except Exception as e:
            print(f"[Deriv] Connection failed: {e}")
            self.authorized = False
            asyncio.create_task(self._retry_connect())

    async def _retry_connect(self, delay: float = 5.0):
        await asyncio.sleep(delay)
        if not self.authorized and self.running:
            print("[Deriv] Retrying connection...")
            await self.connect()

    async def authorize(self):
        try:
            response = await self.api.authorize(self.token)
            if "authorize" in response:
                self.authorized = True
                self.balance = response["authorize"]["balance"]
                if "balance" in self.callbacks:
                    await self.callbacks["balance"](self.balance)
            return response
        except APIError as e:
            return {"error": str(e)}

    async def _heartbeat(self):
        while self.running:
            try:
                await asyncio.sleep(30)
                if self.api:
                    await self.api.send({"ping": 1})
            except Exception as e:
                print(f"[Deriv] Heartbeat error: {e}")

    async def subscribe_ticks(self, symbol: str):
        if not self.authorized or not self.api:
            return
        try:
            src = await self.api.subscribe({"ticks": symbol})
            self._sources[f"tick_{symbol}"] = src
            self._subs[f"tick_{symbol}"] = src.subscribe(lambda msg: self._handle_tick(msg, symbol))
        except Exception as e:
            print(f"[Deriv] Tick subscribe error: {e}")

    def _handle_tick(self, msg, symbol):
        if "tick" in msg and "tick" in self.callbacks:
            tick = msg["tick"]
            asyncio.create_task(self.callbacks["tick"](tick))

    async def subscribe_candles(self, symbol: str, granularity: int = 60):
        if not self.authorized or not self.api:
            return
        try:
            response = await self.api.send({
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": 100,
                "end": "latest",
                "start": 1,
                "style": "candles",
                "granularity": granularity
            })
            if "candles" in response and "candles" in self.callbacks:
                asyncio.create_task(self.callbacks["candles"](response))
        except Exception as e:
            print(f"[Deriv] Candles error: {e}")

    async def get_proposal(self, proposal_data: dict) -> dict:
        if not self.authorized or not self.api:
            return {"error": "not authorized"}
        try:
            return await self.api.proposal(proposal_data)
        except APIError as e:
            return {"error": str(e)}

    async def buy_contract(self, proposal_id: str, price: float) -> dict:
        if not self.authorized or not self.api:
            return {"error": "not authorized"}
        try:
            return await self.api.buy({"buy": proposal_id, "price": price})
        except APIError as e:
            return {"error": str(e)}

    async def sell_contract(self, contract_id: str) -> dict:
        if not self.authorized or not self.api:
            return {"error": "not authorized"}
        try:
            return await self.api.sell({"sell": contract_id})
        except APIError as e:
            return {"error": str(e)}

    async def subscribe_contract_updates(self, contract_id: str):
        if not self.authorized or not self.api:
            return
        try:
            src = await self.api.subscribe({"proposal_open_contract": 1, "contract_id": contract_id, "subscribe": 1})
            self._sources[f"contract_{contract_id}"] = src
            self._subs[f"contract_{contract_id}"] = src.subscribe(lambda msg: self._handle_contract(msg))
        except Exception as e:
            print(f"[Deriv] Contract subscribe error: {e}")

    def _handle_contract(self, msg):
        if "proposal_open_contract" in msg and "contract_update" in self.callbacks:
            asyncio.create_task(self.callbacks["contract_update"](msg["proposal_open_contract"]))

    async def close(self):
        self.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        for sub in self._subs.values():
            try:
                sub.dispose()
            except:
                pass
        self._subs.clear()
        self._sources.clear()