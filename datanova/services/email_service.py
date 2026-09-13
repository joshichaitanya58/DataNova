import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)


def _clean_env_val(val: str) -> str:
    if not val:
        return ""
    val = str(val).strip()
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1].strip()
    return val


def send_smtp_email(to_email: str, subject: str, body_text: str, body_html: str = None, override_settings: dict = None) -> tuple:
    """
    Sends an email using configured SMTP settings from SYSTEM_SETTINGS and environment variables.
    Returns (success_boolean, message_string).
    """
    try:
        settings = override_settings if override_settings is not None else current_app.config.get('SYSTEM_SETTINGS', {})

        # 1. Resolve Host
        smtp_host = (
            settings.get('smtp_host')
            or _clean_env_val(os.getenv('MAIL_SERVER'))
            or _clean_env_val(os.getenv('SMTP_HOST'))
            or 'smtp.gmail.com'
        )

        # 2. Resolve Port
        raw_port = (
            settings.get('smtp_port')
            or _clean_env_val(os.getenv('MAIL_PORT'))
            or _clean_env_val(os.getenv('SMTP_PORT'))
            or '587'
        )
        try:
            smtp_port = int(raw_port)
        except (ValueError, TypeError):
            smtp_port = 587

        # 3. Resolve Sender Email
        sender_email = (
            settings.get('sender_email')
            or _clean_env_val(os.getenv('MAIL_DEFAULT_SENDER'))
            or _clean_env_val(os.getenv('SENDER_EMAIL'))
            or _clean_env_val(os.getenv('MAIL_USERNAME'))
            or 'noreply@datanova.com'
        )

        # 4. Resolve Username & Password
        mail_user = (
            settings.get('smtp_username')
            or _clean_env_val(os.getenv('MAIL_USERNAME'))
            or _clean_env_val(os.getenv('SMTP_USER'))
            or sender_email
        )
        mail_password = (
            settings.get('smtp_password')
            or _clean_env_val(os.getenv('MAIL_PASSWORD'))
            or _clean_env_val(os.getenv('SMTP_PASSWORD'))
            or _clean_env_val(os.getenv('SMTP_PASS'))
            or _clean_env_val(os.getenv('SENDER_PASSWORD'))
        )

        # 5. Resolve Encryption (TLS / SSL / None)
        smtp_encryption = str(settings.get('smtp_encryption', '')).lower().strip()
        if not smtp_encryption:
            if _clean_env_val(os.getenv('MAIL_USE_SSL', '')).lower() in ('true', '1'):
                smtp_encryption = 'ssl'
            elif _clean_env_val(os.getenv('MAIL_USE_TLS', '')).lower() in ('true', '1'):
                smtp_encryption = 'tls'
            else:
                smtp_encryption = 'tls' if smtp_port == 587 else ('ssl' if smtp_port == 465 else 'none')

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email

        part1 = MIMEText(body_text, 'plain')
        msg.attach(part1)

        if body_html:
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)

        # Connect to SMTP server
        if smtp_port == 465 or smtp_encryption == 'ssl':
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if smtp_encryption != 'none':
                server.ehlo()
                server.starttls()
                server.ehlo()

        if mail_password and mail_user:
            server.login(mail_user, mail_password)

        server.sendmail(sender_email, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {to_email} via {smtp_host}:{smtp_port}")
        return True, "Email sent successfully."

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False, f"Email delivery failed: {str(e)}"


def test_smtp_connection(to_email: str, custom_settings: dict = None) -> tuple:
    """
    Tests SMTP configuration by attempting a connection and sending a verification email.
    Returns (success_boolean, message_string).
    """
    subject = "DataNova — SMTP Configuration Verification"
    body_text = "Hello,\n\nThis is a verification email from DataNova Smart Analytics Platform. Your SMTP settings have been validated successfully."
    body_html = """
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px; background-color: #ffffff;">
        <h2 style="color: #2563eb; margin-top: 0;">DataNova Platform</h2>
        <p style="color: #475569; font-size: 14px; line-height: 1.5;">Your SMTP email configuration has been <strong>successfully tested and verified</strong>.</p>
        <div style="background-color: #f1f5f9; padding: 12px; border-radius: 6px; font-size: 12px; color: #334155;">
            <div><strong>Status:</strong> Active & Connected</div>
            <div><strong>Timestamp:</strong> Generated by System Administrator</div>
        </div>
        <p style="color: #94a3b8; font-size: 11px; margin-top: 20px;">DataNova Smart Analytics Platform &bull; Automated System Verification</p>
    </div>
    """
    return send_smtp_email(to_email, subject, body_text, body_html, override_settings=custom_settings)
