from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from contextlib import asynccontextmanager
import asyncpg
import os
import json
import time

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password_rahasia@storage:5432/log_db")

class Event(BaseModel):
    topic: str
    event_id: str
    timestamp: datetime
    source: str
    payload: dict

START_TIME = time.time()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Menghubungkan ke Database")
    try:
        app.state.pool = await asyncpg.create_pool(DATABASE_URL)
        yield
    finally:
        print("Menutup koneksi Database")
        await app.state.pool.close()

app = FastAPI(lifespan=lifespan)

@app.post("/publish")
async def publish_event(event: Event):
    pool = app.state.pool
    async with pool.acquire() as conn:

        result = await conn.fetchval("""
            INSERT INTO processed_events (topic, event_id, timestamp, source, payload)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (topic, event_id) DO NOTHING
            RETURNING event_id
        """, event.topic, event.event_id, event.timestamp, event.source, json.dumps(event.payload))

        if result is None:
            print(f"!!! [DEDUPLIKASI] Event Duplikat Diabaikan: {event.event_id} (Topic: {event.topic})", flush=True)
            
            await conn.execute("UPDATE audit_stats SET counter = counter + 1 WHERE metric_key = 'duplicates_dropped'")
            return {"status": "ignored", "message": "Duplicate event detected and dropped"}

        return {"status": "success", "message": "Event processed"}

@app.get("/stats")
async def get_stats():
    pool = app.state.pool

    uptime_seconds = time.time() - START_TIME

    async with pool.acquire() as conn:
        # Hitung event sukses
        processed_count = await conn.fetchval("SELECT COUNT(*) FROM processed_events")
        
        # Hitung duplikat yang dibuang
        dropped_count = await conn.fetchval("SELECT counter FROM audit_stats WHERE metric_key='duplicates_dropped'")
        
        # Hitung jenis topic yang ada
        topics_count = await conn.fetchval("SELECT COUNT(DISTINCT topic) FROM processed_events")
        
        return {
            "received": (processed_count or 0) + (dropped_count or 0),
            "unique_processed": processed_count or 0,
            "duplicate_dropped": dropped_count or 0,
            "topics_active": topics_count or 0,
            "uptime_seconds": round(uptime_seconds, 2)
        }

@app.get("/events")
async def get_events(limit: int = 10):
    pool = app.state.pool
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM processed_events ORDER BY created_at DESC LIMIT $1", limit)
        return [dict(row) for row in rows]