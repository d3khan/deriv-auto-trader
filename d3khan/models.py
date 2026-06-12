from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Trade(BaseModel):
    id: Optional[int] = None
    session_id: int
    contract_id: Optional[str] = None
    symbol: str
    contract_type: str
    strategy: str
    stake: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    profit: Optional[float] = None
    status: str = "open"
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

class Session(BaseModel):
    id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    initial_balance: float
    final_balance: Optional[float] = None
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    profit: float = 0.0
    status: str = "active"

class EngineState(BaseModel):
    is_running: bool = False
    is_trading_enabled: bool = False
    balance: float = 0.0
    current_session: Optional[Session] = None
    open_contracts: List[Trade] = []
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    win_rate: float = 0.0
    consecutive_losses: int = 0
    current_strategy: str = "ACCU"
    symbol: str = "R_10"
    last_tick: Optional[dict] = None
