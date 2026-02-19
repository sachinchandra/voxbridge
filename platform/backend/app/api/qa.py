"""Quality Assurance API routes.

Provides automated call scoring, flagged call listing,
QA summary statistics, and manual call review.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger

from app.middleware.auth import get_current_customer
from app.models.database import (
    CallQAScore,
    Customer,
    QAScoreResponse,
    QASummary,
)
from app.services.database import (
    create_qa_score,
    get_call,
    get_agent,
    get_enhanced_analytics,
    get_qa_score_for_call,
    get_qa_summary,
    list_calls,
    list_qa_scores,
)
from app.services.qa_scorer import score_call

router = APIRouter(prefix="/qa", tags=["Quality Assurance"])


# ──────────────────────────────────────────────────────────────────
# Score a call
# ──────────────────────────────────────────────────────────────────

@router.post("/score/{call_id}", response_model=QAScoreResponse)
async def score_call_endpoint(
    call_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Run QA scoring on a specific call.

    If the call has already been scored, returns the existing score.
    Otherwise runs the automated scoring pipeline and stores the result.
    """
    # Check if already scored
    existing = get_qa_score_for_call(call_id)
    if existing:
        return _to_response(existing)

    # Get the call
    call = get_call(call_id, customer.id)
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found",
        )

    # Get agent's system prompt for compliance scoring
    agent = get_agent(call.agent_id, customer.id)
    system_prompt = agent.system_prompt if agent else ""

    # Score the call
    scores = score_call(
        transcript=call.transcript,
        resolution=call.resolution,
        escalated=call.escalated_to_human,
        sentiment_score=call.sentiment_score,
        system_prompt=system_prompt,
    )

    # Store the score
    qa_score = create_qa_score({
        "call_id": call_id,
        "customer_id": customer.id,
        "agent_id": call.agent_id,
        **scores,
    })

    logger.info(f"QA scored call {call_id}: overall={qa_score.overall_score}, flagged={qa_score.flagged}")
    return _to_response(qa_score)


# ──────────────────────────────────────────────────────────────────
# Batch score recent calls
# ──────────────────────────────────────────────────────────────────

@router.post("/score-batch")
async def score_batch(
    limit: int = Query(50, ge=1, le=200, description="Max calls to score"),
    customer: Customer = Depends(get_current_customer),
):
    """Score recent unscored calls in batch.

    Finds calls that haven't been QA scored yet and runs the scorer.
    """
    calls, total = list_calls(customer.id, limit=limit, offset=0)
    scored = 0
    flagged = 0

    for call in calls:
        # Skip if already scored
        existing = get_qa_score_for_call(call.id)
        if existing:
            continue

        # Skip calls that haven't completed
        if call.status not in ("completed", "failed"):
            continue

        # Get agent system prompt
        agent = get_agent(call.agent_id, customer.id)
        system_prompt = agent.system_prompt if agent else ""

        # Score
        scores = score_call(
            transcript=call.transcript,
            resolution=call.resolution,
            escalated=call.escalated_to_human,
            sentiment_score=call.sentiment_score,
            system_prompt=system_prompt,
        )

        qa_score = create_qa_score({
            "call_id": call.id,
            "customer_id": customer.id,
            "agent_id": call.agent_id,
            **scores,
        })

        scored += 1
        if qa_score.flagged:
            flagged += 1

    return {
        "scored": scored,
        "flagged": flagged,
        "message": f"Scored {scored} calls, {flagged} flagged for review",
    }


# ──────────────────────────────────────────────────────────────────
# Get score for a call
# ──────────────────────────────────────────────────────────────────

@router.get("/calls/{call_id}", response_model=QAScoreResponse | None)
async def get_call_qa_score(
    call_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Get the QA score for a specific call."""
    score = get_qa_score_for_call(call_id)
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QA score not found. Run POST /qa/score/{call_id} first.",
        )
    return _to_response(score)


# ──────────────────────────────────────────────────────────────────
# List scores (with filters)
# ──────────────────────────────────────────────────────────────────

@router.get("/scores")
async def list_scores(
    agent_id: str | None = Query(None, description="Filter by agent"),
    flagged: bool = Query(False, description="Show only flagged calls"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    customer: Customer = Depends(get_current_customer),
):
    """List QA scores with optional filters."""
    scores, total = list_qa_scores(
        customer_id=customer.id,
        agent_id=agent_id,
        flagged_only=flagged,
        limit=limit,
        offset=offset,
    )
    return {
        "scores": [_to_response(s) for s in scores],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ──────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=QASummary)
async def get_summary(
    agent_id: str | None = Query(None, description="Filter by agent"),
    customer: Customer = Depends(get_current_customer),
):
    """Get QA summary statistics for the dashboard."""
    summary = get_qa_summary(customer.id, agent_id=agent_id)
    return QASummary(**summary)


# ──────────────────────────────────────────────────────────────────
# Enhanced Analytics
# ──────────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics(
    customer: Customer = Depends(get_current_customer),
):
    """Get enhanced analytics with sentiment, peak hours, escalation reasons."""
    return get_enhanced_analytics(customer.id)


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _to_response(score: CallQAScore) -> QAScoreResponse:
    return QAScoreResponse(
        id=score.id,
        call_id=score.call_id,
        agent_id=score.agent_id,
        accuracy_score=score.accuracy_score,
        tone_score=score.tone_score,
        resolution_score=score.resolution_score,
        compliance_score=score.compliance_score,
        overall_score=score.overall_score,
        pii_detected=score.pii_detected,
        angry_caller=score.angry_caller,
        flagged=score.flagged,
        flag_reasons=score.flag_reasons,
        summary=score.summary,
        improvement_suggestions=score.improvement_suggestions,
        created_at=score.created_at,
    )
