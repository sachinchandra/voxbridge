"""Weekly QA Summary Email service.

Generates and sends weekly QA reports to customers summarizing their
AI agent call quality metrics. Designed to be triggered by a cron job
or scheduler endpoint.

Email delivery uses SMTP (configurable) with HTML templates.
Falls back to logging the report if SMTP is not configured.
"""

from __future__ import annotations

import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from loguru import logger

from app.models.database import QAWeeklyReport


# ──────────────────────────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────────────────────────

def generate_weekly_report(
    customer_id: str,
    customer_email: str,
    customer_name: str,
    qa_summary: dict[str, Any],
    agent_stats: list[dict[str, Any]] | None = None,
    previous_avg: float | None = None,
) -> QAWeeklyReport:
    """Build a QAWeeklyReport from QA summary data.

    Args:
        customer_id: Customer UUID.
        customer_email: Recipient email.
        customer_name: Customer display name.
        qa_summary: Output from get_qa_summary() database function.
        agent_stats: Optional per-agent breakdown.
        previous_avg: Previous week's average score for trend calculation.
    """
    now = datetime.now(timezone.utc)
    period_end = now.strftime("%Y-%m-%d")
    period_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    # Determine score trend
    current_avg = qa_summary.get("avg_overall", 0.0)
    if previous_avg is not None and previous_avg > 0:
        diff = current_avg - previous_avg
        if diff > 2:
            trend = "improving"
        elif diff < -2:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Top issues from flag reasons
    top_issues = [
        r["reason"]
        for r in qa_summary.get("top_flag_reasons", [])[:5]
        if r.get("reason")
    ]

    # Top agents
    top_agents = []
    if agent_stats:
        sorted_agents = sorted(agent_stats, key=lambda a: a.get("avg_score", 0), reverse=True)
        for a in sorted_agents[:5]:
            top_agents.append({
                "name": a.get("agent_name", "Unknown"),
                "score": round(a.get("avg_score", 0), 1),
                "calls": a.get("total_calls", 0),
            })

    # Improvement suggestions based on lowest category scores
    improvement_areas = []
    categories = {
        "Accuracy": qa_summary.get("avg_accuracy", 100),
        "Tone": qa_summary.get("avg_tone", 100),
        "Resolution": qa_summary.get("avg_resolution", 100),
        "Compliance": qa_summary.get("avg_compliance", 100),
    }
    for cat, score in sorted(categories.items(), key=lambda x: x[1]):
        if score < 70:
            improvement_areas.append(f"{cat} scores are low ({score:.0f}/100) — review agent prompts and training data")
        elif score < 80:
            improvement_areas.append(f"{cat} could be improved ({score:.0f}/100)")

    if qa_summary.get("pii_count", 0) > 0:
        improvement_areas.append(f"PII detected in {qa_summary['pii_count']} calls — review data handling procedures")
    if qa_summary.get("angry_count", 0) > 0:
        improvement_areas.append(f"{qa_summary['angry_count']} angry callers detected — consider adjusting escalation thresholds")

    return QAWeeklyReport(
        customer_id=customer_id,
        customer_email=customer_email,
        customer_name=customer_name,
        period_start=period_start,
        period_end=period_end,
        total_calls_scored=qa_summary.get("total_scored", 0),
        avg_overall_score=round(current_avg, 1),
        avg_accuracy=round(qa_summary.get("avg_accuracy", 0), 1),
        avg_tone=round(qa_summary.get("avg_tone", 0), 1),
        avg_resolution=round(qa_summary.get("avg_resolution", 0), 1),
        avg_compliance=round(qa_summary.get("avg_compliance", 0), 1),
        flagged_calls=qa_summary.get("flagged_count", 0),
        pii_detections=qa_summary.get("pii_count", 0),
        angry_callers=qa_summary.get("angry_count", 0),
        top_issues=top_issues,
        top_agents=top_agents,
        improvement_areas=improvement_areas,
        score_trend=trend,
    )


# ──────────────────────────────────────────────────────────────────
# HTML email template
# ──────────────────────────────────────────────────────────────────

def render_email_html(report: QAWeeklyReport) -> str:
    """Render the weekly QA report as an HTML email."""

    def score_color(score: float) -> str:
        if score >= 80:
            return "#22c55e"
        if score >= 60:
            return "#eab308"
        return "#ef4444"

    trend_icon = {"improving": "&#9650;", "declining": "&#9660;", "stable": "&#9644;"}
    trend_color = {"improving": "#22c55e", "declining": "#ef4444", "stable": "#9ca3af"}

    agents_html = ""
    for i, agent in enumerate(report.top_agents[:5], 1):
        agents_html += f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #2d2250;">#{i}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #2d2250;">{agent['name']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #2d2250;color:{score_color(agent['score'])}">{agent['score']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #2d2250;">{agent['calls']}</td>
        </tr>"""

    issues_html = ""
    for issue in report.top_issues[:5]:
        issues_html += f'<li style="margin-bottom:4px;color:#d1d5db;">{issue}</li>'

    improvements_html = ""
    for area in report.improvement_areas[:5]:
        improvements_html += f'<li style="margin-bottom:4px;color:#d1d5db;">{area}</li>'

    alert_section = ""
    if report.flagged_calls > 0 or report.pii_detections > 0:
        alert_section = f"""
        <div style="background:#451a1a;border:1px solid #7f1d1d;border-radius:8px;padding:16px;margin-bottom:24px;">
            <h3 style="color:#fca5a5;margin:0 0 8px 0;font-size:14px;">Alerts</h3>
            <p style="color:#d1d5db;margin:0;font-size:13px;">
                {report.flagged_calls} flagged calls
                {f' &bull; {report.pii_detections} PII detections' if report.pii_detections else ''}
                {f' &bull; {report.angry_callers} angry callers' if report.angry_callers else ''}
            </p>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0f0a1e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:24px;">

    <!-- Header -->
    <div style="text-align:center;padding:24px 0;border-bottom:1px solid #2d2250;">
        <h1 style="color:#a78bfa;margin:0;font-size:24px;">VoxBridge</h1>
        <p style="color:#9ca3af;margin:8px 0 0;font-size:13px;">Weekly QA Report &bull; {report.period_start} to {report.period_end}</p>
    </div>

    <div style="padding:24px 0;">
        <p style="color:#e5e7eb;font-size:15px;margin:0 0 24px;">
            Hi {report.customer_name or 'there'},<br><br>
            Here's your weekly call quality summary.
        </p>

        <!-- Overall Score -->
        <div style="background:#1a1230;border:1px solid #2d2250;border-radius:12px;padding:24px;text-align:center;margin-bottom:24px;">
            <p style="color:#9ca3af;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin:0 0 8px;">Overall Quality Score</p>
            <p style="color:{score_color(report.avg_overall_score)};font-size:48px;font-weight:700;margin:0;">
                {report.avg_overall_score}
            </p>
            <p style="color:{trend_color.get(report.score_trend, '#9ca3af')};font-size:14px;margin:8px 0 0;">
                {trend_icon.get(report.score_trend, '')} {report.score_trend.capitalize()} vs last week
            </p>
            <p style="color:#6b7280;font-size:13px;margin:8px 0 0;">
                {report.total_calls_scored} calls scored
            </p>
        </div>

        <!-- Category Scores -->
        <div style="display:flex;gap:12px;margin-bottom:24px;">
            <div style="flex:1;background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;text-align:center;">
                <p style="color:#9ca3af;font-size:11px;margin:0;">Accuracy</p>
                <p style="color:{score_color(report.avg_accuracy)};font-size:24px;font-weight:600;margin:4px 0 0;">{report.avg_accuracy}</p>
            </div>
            <div style="flex:1;background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;text-align:center;">
                <p style="color:#9ca3af;font-size:11px;margin:0;">Tone</p>
                <p style="color:{score_color(report.avg_tone)};font-size:24px;font-weight:600;margin:4px 0 0;">{report.avg_tone}</p>
            </div>
            <div style="flex:1;background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;text-align:center;">
                <p style="color:#9ca3af;font-size:11px;margin:0;">Resolution</p>
                <p style="color:{score_color(report.avg_resolution)};font-size:24px;font-weight:600;margin:4px 0 0;">{report.avg_resolution}</p>
            </div>
            <div style="flex:1;background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;text-align:center;">
                <p style="color:#9ca3af;font-size:11px;margin:0;">Compliance</p>
                <p style="color:{score_color(report.avg_compliance)};font-size:24px;font-weight:600;margin:4px 0 0;">{report.avg_compliance}</p>
            </div>
        </div>

        {alert_section}

        <!-- Top Agents -->
        {'<div style="background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;margin-bottom:24px;">' +
         '<h3 style="color:#e5e7eb;margin:0 0 12px;font-size:14px;">Top Agents</h3>' +
         '<table style="width:100%;border-collapse:collapse;color:#e5e7eb;font-size:13px;">' +
         '<tr style="color:#9ca3af;"><th style="text-align:left;padding:8px 12px;">Rank</th><th style="text-align:left;padding:8px 12px;">Agent</th><th style="text-align:left;padding:8px 12px;">Score</th><th style="text-align:left;padding:8px 12px;">Calls</th></tr>' +
         agents_html +
         '</table></div>' if agents_html else ''}

        <!-- Top Issues -->
        {'<div style="background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;margin-bottom:24px;">' +
         '<h3 style="color:#e5e7eb;margin:0 0 12px;font-size:14px;">Top Flag Reasons</h3>' +
         '<ul style="margin:0;padding-left:20px;">' + issues_html + '</ul></div>' if issues_html else ''}

        <!-- Improvements -->
        {'<div style="background:#1a1230;border:1px solid #2d2250;border-radius:8px;padding:16px;margin-bottom:24px;">' +
         '<h3 style="color:#e5e7eb;margin:0 0 12px;font-size:14px;">Areas for Improvement</h3>' +
         '<ul style="margin:0;padding-left:20px;">' + improvements_html + '</ul></div>' if improvements_html else ''}

        <!-- CTA -->
        <div style="text-align:center;padding:24px 0;">
            <a href="https://app.voxbridge.ai/dashboard/qa" style="display:inline-block;background:#7c3aed;color:white;text-decoration:none;padding:12px 32px;border-radius:8px;font-weight:600;font-size:14px;">
                View Full QA Dashboard
            </a>
        </div>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid #2d2250;padding:16px 0;text-align:center;">
        <p style="color:#6b7280;font-size:11px;margin:0;">
            VoxBridge AI Contact Center &bull; You're receiving this because you have QA reports enabled.
            <br>
            <a href="https://app.voxbridge.ai/dashboard/billing" style="color:#7c3aed;">Manage preferences</a>
        </p>
    </div>
</div>
</body>
</html>"""


# ──────────────────────────────────────────────────────────────────
# Email sending
# ──────────────────────────────────────────────────────────────────

def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_pass: str = "",
    from_email: str = "reports@voxbridge.ai",
) -> bool:
    """Send an HTML email via SMTP.

    Returns True if sent successfully, False otherwise.
    If SMTP is not configured, logs the email instead.
    """
    if not smtp_host or not smtp_user:
        logger.info(f"SMTP not configured — email to {to_email} logged instead")
        logger.info(f"Subject: {subject}")
        logger.debug(f"Body length: {len(html_body)} chars")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email

        # Plain text fallback
        plain = f"VoxBridge Weekly QA Report\n\nView your full report at https://app.voxbridge.ai/dashboard/qa"
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_email, [to_email], msg.as_string())

        logger.info(f"Weekly QA email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_weekly_report(report: QAWeeklyReport, smtp_config: dict | None = None) -> bool:
    """Generate HTML and send the weekly QA report email."""
    html = render_email_html(report)
    subject = f"VoxBridge QA Report — Week of {report.period_start} (Score: {report.avg_overall_score})"

    config = smtp_config or {}
    return send_email(
        to_email=report.customer_email,
        subject=subject,
        html_body=html,
        smtp_host=config.get("host", ""),
        smtp_port=config.get("port", 587),
        smtp_user=config.get("user", ""),
        smtp_pass=config.get("pass", ""),
    )
