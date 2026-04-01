"""
Session API routes.

Endpoints for managing conversation sessions.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()

# In-memory session store (will be replaced with database)
_sessions: dict[str, dict[str, Any]] = {}


class SessionCreate(BaseModel):
    """Request model for creating a session."""

    name: str | None = Field(None, description="Optional session name")
    metadata: dict[str, Any] | None = Field(None, description="Session metadata")


class SessionInfo(BaseModel):
    """Session information model."""

    id: str
    name: str | None
    created_at: str
    updated_at: str
    message_count: int
    status: str


class Message(BaseModel):
    """Message model."""

    id: str
    session_id: str
    role: str
    content: str
    timestamp: str


class MessageCreate(BaseModel):
    """Request model for creating a message."""

    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")


@router.post("/", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def create_session(request: SessionCreate) -> SessionInfo:
    """
    Create a new session.

    Creates a new conversation session and returns its information.
    """
    session_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    _sessions[session_id] = {
        "id": session_id,
        "name": request.name,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "status": "active",
        "messages": [],
        "metadata": request.metadata or {},
    }

    return SessionInfo(
        id=session_id,
        name=request.name,
        created_at=now,
        updated_at=now,
        message_count=0,
        status="active",
    )


@router.get("/", response_model=list[SessionInfo])
async def list_sessions() -> list[SessionInfo]:
    """
    List all sessions.

    Returns a list of all sessions.
    """
    return [
        SessionInfo(
            id=s["id"],
            name=s.get("name"),
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            message_count=s["message_count"],
            status=s["status"],
        )
        for s in _sessions.values()
    ]


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str) -> SessionInfo:
    """
    Get session information.

    Returns detailed information about the specified session.
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    s = _sessions[session_id]
    return SessionInfo(
        id=s["id"],
        name=s.get("name"),
        created_at=s["created_at"],
        updated_at=s["updated_at"],
        message_count=s["message_count"],
        status=s["status"],
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str) -> None:
    """
    Delete a session.

    Deletes the specified session and all its messages.
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    del _sessions[session_id]


@router.get("/{session_id}/messages", response_model=list[Message])
async def get_messages(session_id: str) -> list[Message]:
    """
    Get session messages.

    Returns all messages in the specified session.
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    return _sessions[session_id]["messages"]


@router.post(
    "/{session_id}/messages",
    response_model=Message,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(session_id: str, request: MessageCreate) -> Message:
    """
    Add a message to a session.

    Adds a new message to the specified session.
    """
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )

    message_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    message = Message(
        id=message_id,
        session_id=session_id,
        role=request.role,
        content=request.content,
        timestamp=now,
    )

    _sessions[session_id]["messages"].append(message.model_dump())
    _sessions[session_id]["message_count"] += 1
    _sessions[session_id]["updated_at"] = now

    return message
