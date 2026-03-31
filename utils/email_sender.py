"""
Email Alert System — Sends alert emails via SMTP configured through UI.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pandas as pd
from utils.database import get_db, get_setting


def get_smtp_config():
    """Load SMTP config from database."""
    return {
        "server": get_setting("smtp_server", ""),
        "port": int(get_setting("smtp_port", "587")),
        "username": get_setting("smtp_username", ""),
        "password": get_setting("smtp_password", ""),
        "sender_name": get_setting("smtp_sender_name", "CityBCPAgent"),
        "sender_email": get_setting("smtp_sender_email", ""),
        "use_tls": get_setting("smtp_use_tls", "true") == "true",
        "enabled": get_setting("smtp_enabled", "false") == "true",
    }


def is_email_configured():
    """Check if SMTP is configured and enabled."""
    config = get_smtp_config()
    return (config["enabled"] and config["server"] and
            config["username"] and config["password"] and config["sender_email"])


def get_recipients(severity=None):
    """Get active recipients, optionally filtered by severity preference."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM alert_recipients WHERE is_active = 1"
        ).fetchall()

    recipients = []
    for r in rows:
        if severity:
            allowed = (r["severity_filter"] or "CRITICAL,WARNING").split(",")
            if severity not in allowed:
                continue
        recipients.append(dict(r))
    return recipients


def send_test_email(to_email):
    """Send a test email to verify SMTP configuration."""
    config = get_smtp_config()
    if not config["server"]:
        return False, "SMTP server not configured"

    subject = "CityBCPAgent — Test Email"
    body = f"""
    <h2>CityBCPAgent Email Test</h2>
    <p>This is a test email from City BCP Agent.</p>
    <p>If you received this, your email alerts are working correctly.</p>
    <p><strong>Sent at:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    """

    return _send_email(config, to_email, subject, body)


def send_alert_email(alerts_df):
    """
    Send alert notification to all configured recipients.
    Returns (sent_count, errors).
    """
    if not is_email_configured():
        return 0, ["Email not configured"]

    if alerts_df.empty:
        return 0, []

    config = get_smtp_config()
    errors = []
    sent = 0

    # Group alerts by severity
    critical = alerts_df[alerts_df["severity"] == "CRITICAL"]
    warnings = alerts_df[alerts_df["severity"] == "WARNING"]
    info = alerts_df[alerts_df["severity"] == "INFO"]

    # Build email
    subject = f"🚨 CityBCPAgent Alert — {len(critical)} Critical, {len(warnings)} Warning"

    body = _build_alert_html(critical, warnings, info)

    # Send to each recipient
    for recipient in get_recipients():
        # Filter by severity preference
        allowed = (recipient["severity_filter"] or "CRITICAL,WARNING").split(",")
        relevant = alerts_df[alerts_df["severity"].isin(allowed)]
        if relevant.empty:
            continue

        # Filter by sector if specified
        if recipient.get("sectors"):
            sector_list = recipient["sectors"].split(",")
            relevant = relevant[
                relevant["sector_id"].isin(sector_list) |
                relevant["sector_id"].isna()
            ]
            if relevant.empty:
                continue

        # Build recipient-specific email
        r_critical = relevant[relevant["severity"] == "CRITICAL"]
        r_warnings = relevant[relevant["severity"] == "WARNING"]
        r_info = relevant[relevant["severity"] == "INFO"]
        r_subject = f"🚨 CityBCPAgent — {len(r_critical)} Critical, {len(r_warnings)} Warning alerts"
        r_body = _build_alert_html(r_critical, r_warnings, r_info, recipient["name"])

        success, error = _send_email(config, recipient["email"], r_subject, r_body)

        # Log
        with get_db() as conn:
            conn.execute("""
                INSERT INTO email_log (recipient, subject, alert_count, status, error)
                VALUES (?, ?, ?, ?, ?)
            """, (recipient["email"], r_subject, len(relevant),
                  "sent" if success else "failed", error))

        if success:
            sent += 1
        else:
            errors.append(f"{recipient['email']}: {error}")

    return sent, errors


def _build_alert_html(critical, warnings, info, recipient_name=None):
    """Build HTML email body from alert DataFrames."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    greeting = f"<p>Hi {recipient_name},</p>" if recipient_name else ""

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #1e3a5f, #0f172a); color: white;
                    padding: 20px; border-radius: 10px 10px 0 0;">
            <h2 style="margin:0">🛡️ CityBCPAgent Alert Report</h2>
            <p style="margin:5px 0 0;opacity:0.8">{now}</p>
        </div>
        <div style="padding: 20px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0 0 10px 10px;">
        {greeting}
    """

    if not critical.empty:
        html += '<h3 style="color:#dc2626">🔴 CRITICAL ALERTS — Immediate Action Required</h3>'
        html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px">'
        html += '<tr style="background:#fef2f2"><th style="padding:8px;text-align:left;border-bottom:2px solid #dc2626">Site</th><th style="padding:8px;text-align:left;border-bottom:2px solid #dc2626">Alert</th></tr>'
        for _, row in critical.iterrows():
            site = row.get("site_id", "") or row.get("sector_id", "")
            html += f'<tr><td style="padding:8px;border-bottom:1px solid #eee"><strong>{site}</strong></td><td style="padding:8px;border-bottom:1px solid #eee">{row["message"]}</td></tr>'
        html += '</table>'

    if not warnings.empty:
        html += '<h3 style="color:#d97706">🟡 WARNING ALERTS</h3>'
        html += '<table style="width:100%;border-collapse:collapse;margin-bottom:20px">'
        html += '<tr style="background:#fffbeb"><th style="padding:8px;text-align:left;border-bottom:2px solid #d97706">Site</th><th style="padding:8px;text-align:left;border-bottom:2px solid #d97706">Alert</th></tr>'
        for _, row in warnings.head(10).iterrows():
            site = row.get("site_id", "") or row.get("sector_id", "")
            html += f'<tr><td style="padding:8px;border-bottom:1px solid #eee"><strong>{site}</strong></td><td style="padding:8px;border-bottom:1px solid #eee">{row["message"]}</td></tr>'
        if len(warnings) > 10:
            html += f'<tr><td colspan="2" style="padding:8px;color:#6b7280">... and {len(warnings)-10} more warnings</td></tr>'
        html += '</table>'

    if not info.empty:
        html += f'<p style="color:#6b7280">ℹ️ {len(info)} informational alerts (not shown)</p>'

    html += """
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
            <p style="font-size:12px;color:#9ca3af">
                This alert was sent by CityBCPAgent. Login to the dashboard for full details.
            </p>
        </div>
    </body>
    </html>
    """
    return html


def _send_email(config, to_email, subject, html_body):
    """Send an email via SMTP. Returns (success, error_message)."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{config['sender_name']} <{config['sender_email']}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        if config["use_tls"]:
            context = ssl.create_default_context()
            with smtplib.SMTP(config["server"], config["port"], timeout=15) as server:
                server.starttls(context=context)
                server.login(config["username"], config["password"])
                server.sendmail(config["sender_email"], to_email, msg.as_string())
        else:
            with smtplib.SMTP(config["server"], config["port"], timeout=15) as server:
                server.login(config["username"], config["password"])
                server.sendmail(config["sender_email"], to_email, msg.as_string())

        return True, None
    except Exception as e:
        return False, str(e)
