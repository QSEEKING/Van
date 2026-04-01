"""
Agent API routes.

Endpoints for managing AI agents and their interactions.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()


class AgentRequest(BaseModel):
    """Request model for agent interactions."""

    message: str = Field(..., description="User message to process")
    working_dir: str | None = Field(None, description="Working directory")
    context: dict[str, Any] | None = Field(None, description="Additional context")


class AgentResponse(BaseModel):
    """Response model for agent interactions."""

    response: str = Field(..., description="Agent response")
    thinking: str | None = Field(None, description="Agent's reasoning process")
    tools_used: list[str] = Field(default_factory=list, description="Tools used")
    success: bool = Field(..., description="Whether the operation succeeded")


class AgentInfo(BaseModel):
    """Agent information model."""

    name: str
    type: str
    status: str
    capabilities: list[str]


@router.get("/", response_model=list[AgentInfo])
async def list_agents() -> list[AgentInfo]:
    """
    List all available agents.

    Returns a list of all registered agents with their status and capabilities.
    """
    # Placeholder - will be implemented with actual agent registry
    return [
        AgentInfo(
            name="main-agent",
            type="MainAgent",
            status="ready",
            capabilities=["code", "file_operations", "shell"],
        ),
        AgentInfo(
            name="explore-agent",
            type="ExploreAgent",
            status="ready",
            capabilities=["codebase_exploration", "file_search"],
        ),
    ]


@router.post("/process", response_model=AgentResponse)
async def process_request(request: AgentRequest) -> AgentResponse:
    """
    Process a request through the main agent.

    Sends a message to the main agent for processing.
    """
    # Placeholder - will be implemented with actual agent
    return AgentResponse(
        response=f"Processed: {request.message[:50]}...",
        thinking="Analyzing request...",
        tools_used=[],
        success=True,
    )


@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str) -> AgentInfo:
    """
    Get information about a specific agent.

    Returns detailed information about the requested agent.
    """
    # Placeholder - will be implemented with actual agent registry
    if agent_id == "main-agent":
        return AgentInfo(
            name="main-agent",
            type="MainAgent",
            status="ready",
            capabilities=["code", "file_operations", "shell"],
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent '{agent_id}' not found",
    )
