from typing import Optional

from fastapi import APIRouter

from app.api.deps import SessionDep, CurrentUser
from app.models import User
from app.integrations.clawrelay import (
    get_metrics,
    get_sessions,
    get_session_detail,
    get_chat_statistics,
    search_chat_history,
    get_conversation_by_session,
)

router = APIRouter(tags=["metrics"])


@router.get("/metrics", tags=["metrics"])
async def read_metrics(
    session: SessionDep,
    current_user: User = CurrentUser,
) -> dict:
    """Read clawrelay Prometheus metrics"""
    return await get_metrics()


@router.get("/sessions", tags=["metrics"])
async def read_sessions(
    session: SessionDep,
    current_user: User = CurrentUser,
    status: Optional[str] = None,
    bot_key: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Read active session list with filtering and pagination"""
    all_sessions = await get_sessions()

    # Filter
    filtered = all_sessions.get("sessions", [])
    if status:
        filtered = [s for s in filtered if s.get("status") == status]
    if bot_key:
        filtered = [s for s in filtered if s.get("bot_key") == bot_key]

    # Pagination
    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    paginated = filtered[start:end]

    return {
        "sessions": paginated,
        "total": total,
        "page": page,
        "limit": limit,
        "timestamp": all_sessions.get("timestamp"),
    }


@router.get("/sessions/{session_id}", tags=["metrics"])
async def read_session(
    session_id: str,
    session: SessionDep,
    current_user: User = CurrentUser,
) -> dict:
    """Read single session details"""
    return await get_session_detail(session_id)


@router.get("/chat/statistics", tags=["metrics"])
async def read_chat_statistics(
    session: SessionDep,
    current_user: User = CurrentUser,
) -> dict:
    """Read chat statistics from chat.jsonl"""
    return get_chat_statistics()


@router.get("/chat/history", tags=["metrics"])
async def read_chat_history(
    session: SessionDep,
    current_user: User = CurrentUser,
    q: Optional[str] = None,
    user_id: Optional[str] = None,
    bot_key: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """Search chat history from chat.jsonl"""
    return search_chat_history(
        q=q,
        user_id=user_id,
        bot_key=bot_key,
        status=status,
        from_date=from_date,
        to_date=to_date,
        page=page,
        limit=limit,
    )


@router.get("/chat/conversation/{relay_session_id}", tags=["metrics"])
async def read_conversation(
    relay_session_id: str,
    session: SessionDep,
    current_user: User = CurrentUser,
) -> list:
    """Get all messages in a conversation"""
    return get_conversation_by_session(relay_session_id)
