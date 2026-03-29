"""
Read-only data integration for clawrelay-report.

This module is intentionally limited to reading real data from
clawrelay-feishu-server and local chat logs. It must not introduce a
parallel chat execution path.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

CLAWRELAY_BASE_URL = "http://localhost:8088"
CHAT_LOG_PATH = Path("/Users/c/clawrelay-feishu-server/logs/chat.jsonl")


async def get_metrics() -> dict:
    """Read raw metrics text from clawrelay-feishu-server."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CLAWRELAY_BASE_URL}/api/v1/metrics", timeout=10.0)
        resp.raise_for_status()
        return {"metrics_text": resp.text}


async def get_sessions() -> dict:
    """Read active session list from clawrelay-feishu-server.

    Transforms API fields to match frontend Session interface:
    - relay_session_id → session_id
    - user_id → user
    - active → status ("running" | "completed" | "error")
    - created_at: not provided by API, use last_active as proxy
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CLAWRELAY_BASE_URL}/api/v1/sessions", timeout=10.0)
        resp.raise_for_status()

    raw = resp.json()
    transformed_sessions = []
    for s in raw.get("sessions", []):
        # Map active boolean to status string
        active = s.get("active", False)
        status: str
        if active:
            status = "running"
        else:
            status = "completed"

        # created_at not provided by API, use last_active as proxy
        last_active = s.get("last_active", "")
        created_at = last_active

        transformed_sessions.append({
            "session_id": s.get("relay_session_id", ""),
            "user": s.get("user_id", ""),
            "bot_key": s.get("bot_key", ""),
            "status": status,
            "created_at": created_at,
            "last_active": last_active,
        })

    return {
        "sessions": transformed_sessions,
        "total": len(transformed_sessions),
        "timestamp": raw.get("timestamp"),
    }


async def get_session_detail(session_id: str) -> dict:
    """Read a single session detail record."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CLAWRELAY_BASE_URL}/api/v1/sessions/{session_id}", timeout=10.0)
        resp.raise_for_status()
        return resp.json()


def parse_chat_jsonl() -> list[dict]:
    """Parse chat.jsonl into a list of records."""
    if not CHAT_LOG_PATH.exists():
        return []

    records: list[dict] = []
    with open(CHAT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_chat_statistics() -> dict:
    """Aggregate summary statistics from chat.jsonl."""
    records = parse_chat_jsonl()

    if not records:
        return {
            "total_conversations": 0,
            "total_messages": 0,
            "success_count": 0,
            "error_count": 0,
            "avg_latency_ms": 0,
            "total_latency_ms": 0,
            "min_latency_ms": 0,
            "max_latency_ms": 0,
            "success_rate": 100.0,
            "error_rate": 0.0,
            "by_date": [],
            "by_user": [],
            "by_bot": [],
            "recent_errors": [],
            "last_updated": datetime.now().isoformat(),
        }

    total = len(records)
    success_count = sum(1 for r in records if r.get("status") == "success")
    error_count = sum(1 for r in records if r.get("status") == "error")

    latencies = [r.get("latency_ms", 0) for r in records if r.get("latency_ms")]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    min_latency = min(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    total_latency = sum(latencies)

    by_date: dict[str, dict] = {}
    for record in records:
        ts = record.get("timestamp", "")[:10]
        if ts not in by_date:
            by_date[ts] = {
                "date": ts,
                "count": 0,
                "success": 0,
                "error": 0,
                "latency_sum": 0,
            }
        by_date[ts]["count"] += 1
        if record.get("status") == "success":
            by_date[ts]["success"] += 1
        else:
            by_date[ts]["error"] += 1
        by_date[ts]["latency_sum"] += record.get("latency_ms", 0)

    sorted_dates = sorted(by_date.values(), key=lambda item: item["date"], reverse=True)[:7]
    for item in sorted_dates:
        item["avg_latency"] = round(item["latency_sum"] / item["count"], 2) if item["count"] else 0

    by_user: dict[str, dict] = {}
    for record in records:
        user_id = record.get("user_id", "unknown")
        if user_id not in by_user:
            by_user[user_id] = {"user_id": user_id, "count": 0, "success": 0, "error": 0}
        by_user[user_id]["count"] += 1
        if record.get("status") == "success":
            by_user[user_id]["success"] += 1
        else:
            by_user[user_id]["error"] += 1

    by_bot: dict[str, dict] = {}
    for record in records:
        bot_key = record.get("bot_key", "default")
        if bot_key not in by_bot:
            by_bot[bot_key] = {"bot_key": bot_key, "count": 0, "success": 0, "error": 0}
        by_bot[bot_key]["count"] += 1
        if record.get("status") == "success":
            by_bot[bot_key]["success"] += 1
        else:
            by_bot[bot_key]["error"] += 1

    recent_errors = [
        {
            "timestamp": record.get("timestamp"),
            "user_id": record.get("user_id"),
            "error": record.get("error"),
            "message": record.get("message", "")[:100],
        }
        for record in records
        if record.get("status") == "error"
    ][-10:]

    return {
        "total_conversations": total,
        "total_messages": total,
        "success_count": success_count,
        "error_count": error_count,
        "avg_latency_ms": round(avg_latency, 2),
        "total_latency_ms": round(total_latency, 2),
        "min_latency_ms": round(min_latency, 2),
        "max_latency_ms": round(max_latency, 2),
        "success_rate": round(100 * success_count / total, 2) if total > 0 else 100.0,
        "error_rate": round(100 * error_count / total, 2) if total > 0 else 0.0,
        "by_date": sorted_dates,
        "by_user": list(by_user.values()),
        "by_bot": list(by_bot.values()),
        "recent_errors": recent_errors,
        "last_updated": datetime.now().isoformat(),
    }


def search_chat_history(
    q: Optional[str] = None,
    user_id: Optional[str] = None,
    bot_key: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Search chat history from chat.jsonl."""
    records = parse_chat_jsonl()

    if q:
        query = q.lower()
        records = [
            r
            for r in records
            if query in r.get("message", "").lower() or query in r.get("response", "").lower()
        ]

    if user_id:
        records = [r for r in records if r.get("user_id") == user_id]

    if bot_key:
        records = [r for r in records if r.get("bot_key") == bot_key]

    if status:
        records = [r for r in records if r.get("status") == status]

    if from_date:
        records = [r for r in records if r.get("timestamp", "") >= from_date]

    if to_date:
        records = [r for r in records if r.get("timestamp", "") <= to_date]

    records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)

    total = len(records)
    start = (page - 1) * limit
    end = start + limit

    return {
        "results": records[start:end],
        "total": total,
        "page": page,
        "limit": limit,
    }


def get_conversation_by_session(relay_session_id: str) -> list[dict]:
    """Get all messages for a single relay_session_id."""
    records = [r for r in parse_chat_jsonl() if r.get("relay_session_id") == relay_session_id]
    records.sort(key=lambda item: item.get("timestamp", ""))
    return records


# ─── Admin Internal Sessions ─────────────────────────────────────────────────

async def create_admin_session(
    message: str = "",
    owner_id: str = "admin",
    bot_key: str = "_admin_internal",
) -> dict:
    """Create a new admin-managed session via clawrelay-feishu-server admin API."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CLAWRELAY_BASE_URL}/api/v1/admin/sessions",
            json={"message": message, "owner_id": owner_id, "bot_key": bot_key},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()


async def send_admin_message(relay_session_id: str, message: str) -> dict:
    """Send a message to an admin-managed session."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{CLAWRELAY_BASE_URL}/api/v1/admin/sessions/{relay_session_id}/messages",
            json={"message": message},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()


async def get_admin_session_history(relay_session_id: str, limit: int = 50) -> dict:
    """Get message history for an admin-managed session."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{CLAWRELAY_BASE_URL}/api/v1/admin/sessions/{relay_session_id}/history",
            params={"limit": limit},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()


async def list_admin_sessions(owner_id: Optional[str] = None) -> dict:
    """List admin-managed sessions, optionally filtered by owner."""
    async with httpx.AsyncClient() as client:
        params = {"owner_id": owner_id} if owner_id else {}
        resp = await client.get(
            f"{CLAWRELAY_BASE_URL}/api/v1/admin/sessions",
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()


async def rename_admin_session(relay_session_id: str, name: str) -> dict:
    """Rename an admin-managed session."""
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{CLAWRELAY_BASE_URL}/api/v1/admin/sessions/{relay_session_id}",
            json={"name": name},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
