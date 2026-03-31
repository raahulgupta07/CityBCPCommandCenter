"""
Page 10: Settings — SMTP config, alert recipients, email log (all configured via UI)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import streamlit_shadcn_ui as ui
import pandas as pd
from utils.database import get_db, get_setting, set_setting
from utils.email_sender import get_smtp_config, send_test_email, is_email_configured, send_alert_email
from alerts.alert_engine import get_active_alerts
from config.settings import SECTORS

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("⚙️ Settings")

ui.alert(
    title="⚙️ System Configuration",
    description="Configure email alerts, SMTP server, and notification recipients. All settings are stored in the database — no server restart needed.",
    key="alert_settings",
)

selected = ui.tabs(
    options=["📧 Email Setup", "👥 Recipients", "📬 Email Log", "🔧 System"],
    default_value="📧 Email Setup",
    key="settings_tabs",
)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 1: SMTP Configuration
# ═══════════════════════════════════════════════════════════════════════════
if selected == "📧 Email Setup":
    st.markdown("### SMTP Email Configuration")
    st.caption("Configure your email server to send alert notifications. Supports Gmail, Outlook, custom SMTP.")

    # Load current config
    config = get_smtp_config()

    # Quick setup guides
    with st.expander("📘 Quick Setup Guides"):
        st.markdown("""
        **Gmail:**
        - Server: `smtp.gmail.com` | Port: `587` | TLS: Yes
        - Username: your Gmail address
        - Password: [App Password](https://myaccount.google.com/apppasswords) (NOT your regular password)

        **Outlook/Office 365:**
        - Server: `smtp.office365.com` | Port: `587` | TLS: Yes
        - Username: your Outlook email
        - Password: your password or app password

        **Custom SMTP:**
        - Ask your IT team for server, port, and credentials
        """)

    with st.form("smtp_form"):
        st.markdown("#### Server Settings")
        c1, c2, c3 = st.columns(3)
        with c1:
            smtp_server = st.text_input("SMTP Server", value=config["server"],
                                         placeholder="smtp.gmail.com")
        with c2:
            smtp_port = st.number_input("Port", value=config["port"], min_value=1, max_value=65535)
        with c3:
            use_tls = st.checkbox("Use TLS (recommended)", value=config["use_tls"])

        st.markdown("#### Credentials")
        c4, c5 = st.columns(2)
        with c4:
            smtp_user = st.text_input("Username / Email", value=config["username"],
                                       placeholder="alerts@company.com")
        with c5:
            smtp_pass = st.text_input("Password", value=config["password"], type="password",
                                       placeholder="App password or SMTP password")

        st.markdown("#### Sender Info")
        c6, c7 = st.columns(2)
        with c6:
            sender_name = st.text_input("Sender Name", value=config["sender_name"],
                                         placeholder="CityBCPAgent")
        with c7:
            sender_email = st.text_input("Sender Email", value=config["sender_email"],
                                          placeholder="alerts@company.com")

        enabled = st.checkbox("Enable Email Alerts", value=config["enabled"])

        submitted = st.form_submit_button("💾 Save SMTP Settings", use_container_width=True)

        if submitted:
            set_setting("smtp_server", smtp_server)
            set_setting("smtp_port", str(smtp_port))
            set_setting("smtp_username", smtp_user)
            set_setting("smtp_password", smtp_pass)
            set_setting("smtp_sender_name", sender_name)
            set_setting("smtp_sender_email", sender_email)
            set_setting("smtp_use_tls", "true" if use_tls else "false")
            set_setting("smtp_enabled", "true" if enabled else "false")
            st.success("✅ SMTP settings saved!")

    # Test email
    st.markdown("---")
    st.markdown("#### Send Test Email")
    c1, c2 = st.columns([3, 1])
    with c1:
        test_email = st.text_input("Send test to", placeholder="your@email.com", key="test_email")
    with c2:
        st.markdown("")
        if st.button("📨 Send Test", key="btn_test_email", use_container_width=True):
            if test_email:
                with st.spinner("Sending test email..."):
                    success, error = send_test_email(test_email)
                if success:
                    st.success(f"✅ Test email sent to {test_email}")
                else:
                    st.error(f"❌ Failed: {error}")
            else:
                st.warning("Enter an email address first")

    # Status
    st.markdown("---")
    st.markdown("#### Current Status")
    if is_email_configured():
        ui.badges(badge_list=[("Email Alerts", "default"), ("ENABLED", "default")], key="badge_email_on")
    else:
        missing = []
        if not config["server"]:
            missing.append("server")
        if not config["username"]:
            missing.append("username")
        if not config["password"]:
            missing.append("password")
        if not config["sender_email"]:
            missing.append("sender email")
        if not config["enabled"]:
            missing.append("not enabled")
        ui.badges(badge_list=[("Email Alerts", "destructive"), (f"Missing: {', '.join(missing)}", "outline")],
                  key="badge_email_off")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 2: Alert Recipients
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "👥 Recipients":
    st.markdown("### Alert Recipients")
    st.caption("Add people who should receive email alerts. Each person can have different severity and sector filters.")

    # Current recipients
    with get_db() as conn:
        recipients = pd.read_sql_query(
            "SELECT * FROM alert_recipients ORDER BY is_active DESC, name", conn
        )

    if not recipients.empty:
        st.markdown("#### Current Recipients")
        display = recipients[["name", "email", "role", "sectors", "severity_filter", "is_active"]].copy()
        display["is_active"] = display["is_active"].apply(lambda x: "✅ Active" if x else "❌ Disabled")
        display.columns = ["Name", "Email", "Role", "Sectors", "Alert Types", "Status"]
        st.dataframe(display, use_container_width=True, hide_index=True)

    # Add new recipient
    st.markdown("#### Add New Recipient")
    with st.form("add_recipient_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            r_name = st.text_input("Name", placeholder="John Doe")
        with c2:
            r_email = st.text_input("Email", placeholder="john@company.com")
        with c3:
            r_role = st.selectbox("Role", ["Sector Lead", "Manager", "Director", "IT Admin", "Viewer"])

        c4, c5 = st.columns(2)
        with c4:
            r_sectors = st.multiselect("Sectors (leave empty for all)", list(SECTORS.keys()))
        with c5:
            r_severity = st.multiselect("Alert Severity", ["CRITICAL", "WARNING", "INFO"],
                                         default=["CRITICAL", "WARNING"])

        if st.form_submit_button("➕ Add Recipient", use_container_width=True):
            if r_name and r_email:
                with get_db() as conn:
                    conn.execute("""
                        INSERT INTO alert_recipients (name, email, role, sectors, severity_filter)
                        VALUES (?, ?, ?, ?, ?)
                    """, (r_name, r_email, r_role,
                          ",".join(r_sectors) if r_sectors else None,
                          ",".join(r_severity)))
                st.success(f"✅ Added {r_name} ({r_email})")
                st.rerun()
            else:
                st.error("Name and email are required")

    # Remove recipient
    if not recipients.empty:
        st.markdown("#### Manage Recipients")
        c1, c2 = st.columns([3, 1])
        with c1:
            r_to_remove = st.selectbox("Select recipient",
                                        recipients["id"].tolist(),
                                        format_func=lambda x: f"{recipients[recipients['id']==x].iloc[0]['name']} ({recipients[recipients['id']==x].iloc[0]['email']})",
                                        key="remove_recipient")
        with c2:
            st.markdown("")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 Toggle", key="btn_toggle_r"):
                    with get_db() as conn:
                        conn.execute("UPDATE alert_recipients SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
                                     (r_to_remove,))
                    st.rerun()
            with col_b:
                if st.button("🗑️ Delete", key="btn_delete_r"):
                    with get_db() as conn:
                        conn.execute("DELETE FROM alert_recipients WHERE id = ?", (r_to_remove,))
                    st.rerun()

    # Send alerts now
    st.markdown("---")
    st.markdown("#### Send Alert Email Now")
    if st.button("🚨 Send Current Alerts to All Recipients", key="btn_send_alerts",
                 type="primary", use_container_width=True):
        if not is_email_configured():
            st.error("Email not configured. Set up SMTP first.")
        else:
            active_alerts = get_active_alerts()
            if active_alerts.empty:
                st.info("No active alerts to send.")
            else:
                with st.spinner(f"Sending {len(active_alerts)} alerts..."):
                    sent, errors = send_alert_email(active_alerts)
                if sent > 0:
                    st.success(f"✅ Sent to {sent} recipient(s)")
                if errors:
                    for e in errors:
                        st.error(e)

# ═══════════════════════════════════════════════════════════════════════════
# TAB 3: Email Log
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "📬 Email Log":
    st.markdown("### Email Delivery Log")

    with get_db() as conn:
        logs = pd.read_sql_query("""
            SELECT recipient, subject, alert_count, status, error, sent_at
            FROM email_log ORDER BY sent_at DESC LIMIT 50
        """, conn)

    if not logs.empty:
        # Summary
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.metric_card(title="Total Sent", content=str(len(logs[logs["status"] == "sent"])),
                           description="successful", key="mc_email_sent")
        with c2:
            ui.metric_card(title="Failed", content=str(len(logs[logs["status"] == "failed"])),
                           description="delivery errors", key="mc_email_failed")
        with c3:
            latest = logs.iloc[0]["sent_at"] if not logs.empty else "Never"
            ui.metric_card(title="Last Sent", content=str(latest)[:16],
                           description="most recent", key="mc_email_latest")

        logs["status"] = logs["status"].apply(lambda x: "✅ Sent" if x == "sent" else "❌ Failed")
        st.dataframe(logs, use_container_width=True, hide_index=True)
    else:
        st.info("No emails sent yet. Configure SMTP and recipients, then send alerts.")

# ═══════════════════════════════════════════════════════════════════════════
# TAB 4: System Settings
# ═══════════════════════════════════════════════════════════════════════════
elif selected == "🔧 System":
    st.markdown("### System Information")

    with get_db() as conn:
        tables = {}
        for t in ["sectors", "sites", "generators", "daily_operations",
                   "fuel_purchases", "daily_site_summary", "alerts",
                   "alert_recipients", "email_log", "ai_insights_cache", "upload_history"]:
            try:
                tables[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                tables[t] = 0

    st.markdown("#### Database Tables")
    for name, count in tables.items():
        st.caption(f"**{name}**: {count:,} rows")

    st.markdown("---")
    st.markdown("#### All Settings")
    with get_db() as conn:
        settings = pd.read_sql_query(
            "SELECT key, CASE WHEN key LIKE '%password%' THEN '********' ELSE value END as value, updated_at FROM app_settings ORDER BY key",
            conn
        )
    if not settings.empty:
        st.dataframe(settings, use_container_width=True, hide_index=True)
    else:
        st.info("No settings configured yet.")

    st.markdown("---")
    st.markdown("#### Danger Zone")
    if st.button("🗑️ Clear All AI Insights Cache", key="btn_clear_ai"):
        with get_db() as conn:
            conn.execute("DELETE FROM ai_insights_cache")
        st.success("AI insights cache cleared. They will regenerate on next page visit.")

    if st.button("🗑️ Clear All Alerts", key="btn_clear_alerts"):
        with get_db() as conn:
            conn.execute("DELETE FROM alerts")
        st.success("All alerts cleared.")
