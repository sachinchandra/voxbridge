"""QA Email API — trigger and preview weekly QA reports.

Endpoints:
    POST /qa-reports/send          Send weekly report for current customer
    POST /qa-reports/send-all      Send reports for all customers (admin/cron)
    GET  /qa-reports/preview       Preview the email HTML without sending
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.services import database as db
from app.middleware.auth import get_current_customer_id
from app.services.qa_email import generate_weekly_report, render_email_html, send_weekly_report

router = APIRouter(prefix="/qa-reports", tags=["qa-reports"])


@router.post("/send")
async def send_weekly_report_endpoint(
    customer_id: str = Depends(get_current_customer_id),
):
    """Send a weekly QA report email for the current customer."""
    customer = db.get_customer(customer_id)
    if not customer:
        return {"sent": False, "error": "Customer not found"}

    qa_summary = db.get_qa_summary(customer_id)
    report = generate_weekly_report(
        customer_id=customer_id,
        customer_email=customer.email,
        customer_name=customer.name,
        qa_summary=qa_summary,
    )

    sent = send_weekly_report(report)
    return {
        "sent": sent,
        "report": {
            "period": f"{report.period_start} to {report.period_end}",
            "total_scored": report.total_calls_scored,
            "avg_score": report.avg_overall_score,
            "flagged": report.flagged_calls,
            "trend": report.score_trend,
        },
    }


@router.get("/preview")
async def preview_report(
    customer_id: str = Depends(get_current_customer_id),
):
    """Preview the weekly QA report email HTML (for debugging/testing)."""
    customer = db.get_customer(customer_id)
    email = customer.email if customer else "test@example.com"
    name = customer.name if customer else "Test User"

    qa_summary = db.get_qa_summary(customer_id)
    report = generate_weekly_report(
        customer_id=customer_id,
        customer_email=email,
        customer_name=name,
        qa_summary=qa_summary,
    )

    html = render_email_html(report)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


@router.post("/send-all")
async def send_all_reports():
    """Send weekly QA reports to all customers with scored calls.

    Designed to be called by a cron job / scheduler (e.g., every Monday at 9am).
    No auth required — should be protected by API gateway or internal network.
    """
    # In production, iterate over all customers with recent QA data.
    # For now, return a placeholder.
    return {
        "message": "Batch send not yet configured — set up SMTP and cron job",
        "customers_processed": 0,
    }
