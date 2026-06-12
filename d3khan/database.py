import aiosqlite
from typing import Optional, List, Dict, Any

DB_PATH = "d3khan.db"

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("PRAGMA foreign_keys = ON")
        await self._create_tables()
        await self._conn.commit()

    async def _create_tables(self):
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                initial_balance REAL,
                final_balance REAL,
                total_trades INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                profit REAL DEFAULT 0,
                status TEXT DEFAULT 'active'
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                contract_id TEXT,
                symbol TEXT,
                contract_type TEXT,
                strategy TEXT,
                stake REAL,
                entry_price REAL,
                exit_price REAL,
                profit REAL,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT,
                source TEXT
            );
        """)

    async def execute(self, query: str, params: tuple = ()):
        if not self._conn:
            raise RuntimeError("Database not connected")
        return await self._conn.execute(query, params)

    async def commit(self):
        if self._conn:
            await self._conn.commit()

    async def fetchone(self, query: str, params: tuple = ()):
        cursor = await self.execute(query, params)
        return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()):
        cursor = await self.execute(query, params)
        return await cursor.fetchall()
