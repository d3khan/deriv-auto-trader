import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from engine import TradingEngine
from config import *

app = FastAPI(title="d3khan Quant Terminal", version=VERSION)
engine = TradingEngine()

@app.on_event("startup")
async def startup():
    await engine.start()

@app.on_event("shutdown")
async def shutdown():
    if engine._demo_task:
        engine._demo_task.cancel()
    await engine.deriv.close()

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "d3khan Quant Terminal API", "version": VERSION, "demo_mode": engine._demo_mode}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine_running": engine.state.is_running,
        "deriv_connected": engine.deriv.authorized,
        "demo_mode": engine._demo_mode,
        "balance": engine.state.balance,
        "version": VERSION
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    engine.frontend_clients.append(websocket)

    try:
        await websocket.send_json({
            "type": "init",
            "state": engine.state.dict(),
            "version": VERSION,
            "demo_mode": engine._demo_mode
        })

        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            action = msg.get("action")
            if action == "toggle_trading":
                await engine.set_trading_enabled(msg.get("enabled", False))
            elif action == "set_strategy":
                await engine.set_strategy(msg.get("strategy", "ACCU"))
            elif action == "get_stats":
                stats = await engine.get_stats()
                await websocket.send_json({"type": "stats", "stats": stats})
            elif action == "get_logs":
                rows = await engine.db.fetchall(
                    "SELECT * FROM logs ORDER BY timestamp DESC LIMIT 100"
                )
                logs = [{"id": r[0], "timestamp": r[1], "level": r[2], "message": r[3], "source": r[4]} for r in rows]
                await websocket.send_json({"type": "logs", "logs": logs})
            elif action == "clear_cache":
                await engine.db.execute("DELETE FROM logs")
                await engine.db.execute("DELETE FROM trades WHERE status = 'open'")
                await engine.db.commit()
                await websocket.send_json({"type": "cache_cleared"})
            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        if websocket in engine.frontend_clients:
            engine.frontend_clients.remove(websocket)
    except Exception:
        if websocket in engine.frontend_clients:
            engine.frontend_clients.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)