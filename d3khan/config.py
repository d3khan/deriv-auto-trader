import os

# Identity
APP_NAME = "d3khan"
VERSION = "v1.0.0-alpha"
TOKEN = "Vqla5qYgKQ4xIi5" #Fall Back Token: "0VgnvWU66hbBWPS"
APP_ID = 1089

# Trading Config — LOCKED
SYMBOL = "R_10"
CAPITAL = 5.00
STAKE = 0.35
MAX_STAKE = 1.00
GROWTH_RATE = 0.01
TAKE_PROFIT = 0.25
MAX_DAILY_LOSS = 1.00
MAX_CONSECUTIVE_LOSSES = 3

# Indicators
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2.0
EMA_FAST = 8
EMA_SLOW = 21
RSI_PERIOD = 14
DONCHIAN_PERIOD = 20

# Multiplier
MULTIPLIER_TRAILING_STOP = 0.75  # 0.75% trailing stop step

# WebSocket
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3"
FRONTEND_WS_PATH = "/ws"

# Server
PORT = int(os.environ.get("PORT", 8000))
