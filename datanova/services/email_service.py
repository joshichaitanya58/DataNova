import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)


def send_smtp_email(to_email: str, subject: str, body_text: str, body_html: str = None) -> tuple:
    """
    Sends an email using configured SMTP settings from SYSTEM_SETTINGS and environment variables.
    Returns (success_boolean, message_string).
    """
    try:
        settings = current_app.config.get('SYSTEM_SETTINGS', {})
        smtp_host = settings.get('smtp_host', 'smtp.gmail.com')
        smtp_port = int(settings.get('smtp_port', 587))
        sender_email = settings.get('sender_email', 'noreply@datanova.com')

        # Password retrieved from environment
        mail_password = os.getenv('MAIL_PASSWORD') or os.getenv('SMTP_PASSWORD') or os.getenv('SENDER_PASSWORD')

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
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()

        if mail_password:
            mail_user = os.getenv('MAIL_USERNAME', sender_email)
            server.login(mail_user, mail_password)

        server.sendmail(sender_email, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {to_email} via {smtp_host}:{smtp_port}")
        return True, "Email sent successfully."

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False, f"Email delivery failed: {str(e)}"
