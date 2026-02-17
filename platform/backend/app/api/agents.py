"""AI Agent management API routes.

CRUD operations for AI agents + performance stats.
This is the core entity of the AI-first contact center platform.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth import get_current_customer
from app.models.database import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentStatsResponse,
    AgentUpdate,
    Customer,
)
from app.services.database import (
    count_agents,
    create_agent,
    delete_agent,
    get_agent,
    get_agent_stats,
    list_agents,
    list_calls,
    update_agent,
)

router = APIRouter(prefix="/agents", tags=["Agents"])

# Plan-based agent limits
_AGENT_LIMITS = {
    "free": 1,
    "pro": 10,
    "enterprise": 100,
}


def _agent_to_response(agent) -> AgentResponse:
    """Convert an Agent model to an AgentResponse."""
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        status=agent.status,
        system_prompt=agent.system_prompt,
        first_message=agent.first_message,
        end_call_phrases=agent.end_call_phrases,
        stt_provider=agent.stt_provider,
        stt_config=agent.stt_config,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        llm_config=agent.llm_config,
        tts_provider=agent.tts_provider,
        tts_voice_id=agent.tts_voice_id,
        tts_config=agent.tts_config,
        max_duration_seconds=agent.max_duration_seconds,
        interruption_enabled=agent.interruption_enabled,
        tools=agent.tools,
        knowledge_base_id=agent.knowledge_base_id,
        escalation_config=agent.escalation_config,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# ──────────────────────────────────────────────────────────────────
# CRUD Endpoints
# ──────────────────────────────────────────────────────────────────

@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_new_agent(
    body: AgentCreate,
    customer: Customer = Depends(get_current_customer),
):
    """Create a new AI agent."""
    # Check agent limit for plan
    current_count = count_agents(customer.id)
    limit = _AGENT_LIMITS.get(customer.plan.value, 1)
    if current_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent limit reached ({limit}) for your {customer.plan.value} plan. Upgrade to create more agents.",
        )

    agent = create_agent(customer.id, body.model_dump())
    return _agent_to_response(agent)


@router.get("", response_model=list[AgentListResponse])
async def list_all_agents(
    customer: Customer = Depends(get_current_customer),
):
    """List all AI agents for the current customer."""
    agents = list_agents(customer.id)

    result = []
    for agent in agents:
        # Get quick call count for each agent
        calls, total = list_calls(customer.id, agent_id=agent.id, limit=0)
        total_calls = total

        # Get avg duration from recent calls
        recent_calls, _ = list_calls(customer.id, agent_id=agent.id, limit=100)
        avg_dur = 0.0
        if recent_calls:
            avg_dur = sum(c.duration_seconds for c in recent_calls) / len(recent_calls)

        result.append(AgentListResponse(
            id=agent.id,
            name=agent.name,
            status=agent.status,
            llm_provider=agent.llm_provider,
            llm_model=agent.llm_model,
            tts_provider=agent.tts_provider,
            total_calls=total_calls,
            avg_duration=round(avg_dur, 1),
            created_at=agent.created_at,
        ))

    return result


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent_by_id(
    agent_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Get a single AI agent by ID."""
    agent = get_agent(agent_id, customer.id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return _agent_to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent_by_id(
    agent_id: str,
    body: AgentUpdate,
    customer: Customer = Depends(get_current_customer),
):
    """Update an AI agent's configuration."""
    # Verify agent exists
    existing = get_agent(agent_id, customer.id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    updated = update_agent(agent_id, customer.id, body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update agent",
        )
    return _agent_to_response(updated)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_by_id(
    agent_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Delete (archive) an AI agent."""
    success = delete_agent(agent_id, customer.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )


# ──────────────────────────────────────────────────────────────────
# Stats Endpoint
# ──────────────────────────────────────────────────────────────────

@router.get("/{agent_id}/stats", response_model=AgentStatsResponse)
async def get_agent_statistics(
    agent_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Get performance statistics for an AI agent."""
    agent = get_agent(agent_id, customer.id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    stats = get_agent_stats(agent_id, customer.id)

    return AgentStatsResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        **stats,
    )
