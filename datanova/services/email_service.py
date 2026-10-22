import os
import smtplib
import logging
import threading
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import Optional, List, Tuple
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
        if override_settings is not None:
            settings = override_settings
        else:
            try:
                settings = current_app.config.get('SYSTEM_SETTINGS', {}) if current_app else {}
            except Exception:
                settings = {}

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

        msg_root = MIMEMultipart('related')
        msg_root['Subject'] = subject
        msg_root['From'] = f"DataNova Analytics <{sender_email}>"
        msg_root['To'] = to_email

        msg_alt = MIMEMultipart('alternative')
        msg_root.attach(msg_alt)

        part1 = MIMEText(body_text, 'plain')
        msg_alt.attach(part1)

        if body_html:
            part2 = MIMEText(body_html, 'html')
            msg_alt.attach(part2)

        # Attach DataNova logo for inline display in all email clients
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'static', 'assets', 'datanova_logo.png')
        if os.path.exists(logo_path):
            try:
                with open(logo_path, 'rb') as lf:
                    img_data = lf.read()
                logo_img = MIMEImage(img_data)
                logo_img.add_header('Content-ID', '<datanova_logo>')
                logo_img.add_header('Content-Disposition', 'inline', filename='datanova_logo.png')
                msg_root.attach(logo_img)
            except Exception as le:
                logger.warning(f"Could not attach inline logo: {le}")

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

        server.sendmail(sender_email, [to_email], msg_root.as_string())
        server.quit()
        logger.info(f"Successfully sent email to {to_email} via {smtp_host}:{smtp_port}")
        return True, "Email sent successfully."

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False, f"Email delivery failed: {str(e)}"


def send_email_async(to_email: str, subject: str, body_text: str, body_html: str = None):
    """Dispatches email asynchronously in a background thread so web requests respond instantly."""
    app_obj = None
    try:
        app_obj = current_app._get_current_object()
    except Exception:
        app_obj = None

    def _worker():
        if app_obj:
            with app_obj.app_context():
                send_smtp_email(to_email, subject, body_text, body_html)
        else:
            send_smtp_email(to_email, subject, body_text, body_html)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


def parse_client_device(req=None, user_agent: Optional[str] = None, ip_address: Optional[str] = None) -> Tuple[str, str, str]:
    """Parses Flask request or raw user-agent/ip into (device_string, ip_string, location_string)."""
    # 1. IP resolution
    ip = ip_address or '127.0.0.1'
    ua = user_agent or ''

    if req is not None:
        if hasattr(req, 'headers'):
            fwd = req.headers.get('X-Forwarded-For')
            if fwd:
                ip = fwd.split(',')[0].strip()
            elif hasattr(req, 'remote_addr') and req.remote_addr:
                ip = req.remote_addr
            if not ua:
                ua = req.headers.get('User-Agent', '')
        elif isinstance(req, str):
            ua = req

    location = "Localhost / Secure Internal Network" if ip in ('127.0.0.1', '::1', 'localhost', '127.0.0.1:5000') else "Remote Public Network"

    # 2. Browser & OS Parsing
    ua_lower = ua.lower() if ua else ''
    
    browser = "Web Browser"
    if 'edg/' in ua_lower or 'edge/' in ua_lower:
        browser = "Microsoft Edge"
    elif 'chrome/' in ua_lower:
        browser = "Google Chrome"
    elif 'firefox/' in ua_lower:
        browser = "Mozilla Firefox"
    elif 'safari/' in ua_lower and 'chrome' not in ua_lower:
        browser = "Apple Safari"
    elif 'opr/' in ua_lower or 'opera' in ua_lower:
        browser = "Opera"

    os_name = "Desktop"
    if 'windows nt 10.0' in ua_lower:
        os_name = "Windows 10/11"
    elif 'windows' in ua_lower:
        os_name = "Windows"
    elif 'macintosh' in ua_lower or 'mac os x' in ua_lower:
        os_name = "macOS"
    elif 'android' in ua_lower:
        os_name = "Android"
    elif 'iphone' in ua_lower:
        os_name = "iPhone / iOS"
    elif 'ipad' in ua_lower:
        os_name = "iPad / iPadOS"
    elif 'linux' in ua_lower:
        os_name = "Linux"

    return f"{browser} on {os_name}", ip, location


# =====================================================================
# Professional HTML Email Master Layout
# =====================================================================

def _build_master_email(
    badge_text: str,
    badge_bg: str,
    header_title: str,
    header_subtitle: str,
    content_html: str,
    cta_text: Optional[str] = None,
    cta_url: Optional[str] = None,
    secondary_text: Optional[str] = None,
    secondary_url: Optional[str] = None,
    footer_note: Optional[str] = None
) -> str:
    """Builds an executive, responsive, modern HTML email template."""
    year = datetime.now().year

    cta_section = ""
    if cta_text and cta_url:
        cta_section = f"""
        <div style="margin: 28px 0 10px 0; text-align: center;">
            <a href="{cta_url}" style="display: inline-block; background: linear-gradient(135deg, #4F46E5 0%, #3B82F6 100%); color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 13px 32px; border-radius: 6px; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25); letter-spacing: 0.3px;">
                {cta_text} &rarr;
            </a>
        </div>
        """

    secondary_section = ""
    if secondary_text and secondary_url:
        secondary_section = f"""
        <div style="text-align: center; margin-top: 12px;">
            <a href="{secondary_url}" style="color: #64748b; font-size: 12px; text-decoration: underline;">
                {secondary_text}
            </a>
        </div>
        """

    footer_content = footer_note or "This is an automated system notification from DataNova Smart Analytics Platform. Please do not reply directly to this email."

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{header_title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #1e293b;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f1f5f9; padding: 35px 15px;">
        <tr>
            <td align="center">
                <!-- Main Container Card -->
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01); border: 1px solid #e2e8f0;">
                    
                    <!-- Header Banner -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%); padding: 32px 30px; text-align: left;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0">
                                <tr>
                                    <td>
                                        <div style="display: inline-block; background-color: {badge_bg}; color: #ffffff; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; padding: 4px 10px; border-radius: 20px; margin-bottom: 12px;">
                                            {badge_text}
                                        </div>
                                        <h1 style="color: #ffffff; font-size: 22px; font-weight: 700; margin: 0 0 6px 0; letter-spacing: -0.3px;">
                                            {header_title}
                                        </h1>
                                        <p style="color: #cbd5e1; font-size: 13px; margin: 0; line-height: 1.4;">
                                            {header_subtitle}
                                        </p>
                                    </td>
                                    <td align="right" valign="top" style="width: 52px;">
                                        <div style="width: 44px; height: 44px; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25); text-align: center;">
                                            <img src="cid:datanova_logo" width="44" height="44" alt="DataNova" style="display: block; width: 44px; height: 44px; border: 0; outline: none; border-radius: 12px; -ms-interpolation-mode: bicubic;" />
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Body Content -->
                    <tr>
                        <td style="padding: 32px 30px; line-height: 1.6; font-size: 14px; color: #334155;">
                            {content_html}
                            {cta_section}
                            {secondary_section}
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f8fafc; padding: 22px 30px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b; line-height: 1.5;">
                            <div style="font-weight: 600; color: #334155; margin-bottom: 4px;">DataNova Smart Analytics Platform</div>
                            <p style="margin: 0 0 8px 0;">{footer_content}</p>
                            <div style="font-size: 11px; color: #94a3b8;">
                                &copy; {year} DataNova Inc. All rights reserved. &bull; Enterprise Business Intelligence &amp; AI
                            </div>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


# =====================================================================
# Specific Automated Email Handlers
# =====================================================================

def send_welcome_email(user_email: str, first_name: str = 'User', last_name: str = '', role: str = 'Analyst', organization: str = 'General', base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional onboarding welcome email to newly registered users."""
    user_name = f"{first_name or 'User'} {last_name or ''}".strip()
    role_fmt = (role or 'Analyst').capitalize()
    subject = f"🎉 Welcome to DataNova, {first_name}! Your {role_fmt} Account is Ready"

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{user_name}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 20px;">
        Welcome to <strong>DataNova Smart Analytics Platform</strong>. Your new account has been successfully initialized and configured with <strong>{role_fmt}</strong> privileges.
    </p>

    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 20px 0;">
        <table width="100%" cellpadding="4" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">Registered Email:</td>
                <td style="color: #1e293b; font-weight: 600;">{user_email}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Assigned Role:</td>
                <td style="color: #4f46e5; font-weight: 700;">{role_fmt}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Organization:</td>
                <td style="color: #1e293b;">{organization or 'General'}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Account Status:</td>
                <td><span style="background-color: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px;">Active</span></td>
            </tr>
        </table>
    </div>

    <h4 style="color: #0f172a; margin: 22px 0 10px 0; font-size: 14px; font-weight: 700;">🚀 Next Steps in Your Analytics Workspace:</h4>
    <ul style="color: #475569; font-size: 13px; line-height: 1.7; padding-left: 20px; margin-bottom: 20px;">
        <li><strong>Dataset Ingestion:</strong> Drag-and-drop CSV, Excel, or connect live MySQL databases.</li>
        <li><strong>Automated AI EDA:</strong> Instant data summaries, correlation matrix, and anomaly detection.</li>
        <li><strong>Visualization Studio:</strong> Build bespoke interactive charts, pivot dashboards, and export reports.</li>
    </ul>

    <p style="color: #64748b; font-size: 12px; margin-bottom: 0;">
        For your security, please ensure you never share your login credentials with anyone.
    </p>
    """

    body_text = f"Hello {user_name},\n\nWelcome to DataNova! Your {role_fmt} account ({user_email}) is now ready.\nOrganization: {organization}\n\nLog in now: {base_url}/login"
    body_html = _build_master_email(
        badge_text="Welcome Aboard",
        badge_bg="#10B981",
        header_title="Welcome to DataNova",
        header_subtitle="Your high-performance analytics workspace is ready to explore.",
        content_html=content_html,
        cta_text="Access Your Dashboard",
        cta_url=f"{base_url}/login",
        footer_note="If you did not create this account, please immediately contact our platform administrators."
    )

    send_email_async(user_email, subject, body_text, body_html)


def _format_otp_boxes_html(otp_code: str, border_color: str = "#6366F1", text_color: str = "#1E1B4B") -> str:
    """Generates an HTML table of exactly 6 side-by-side digit cards that cannot break onto multiple lines."""
    code_str = str(otp_code).strip()
    cells = []
    for digit in code_str:
        cells.append(f"""
        <td align="center" valign="middle" style="padding: 0 4px; vertical-align: middle;">
            <div style="width: 44px; height: 54px; line-height: 54px; text-align: center; background-color: #ffffff; border: 2px solid {border_color}; border-radius: 9px; font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Courier New', monospace; font-size: 28px; font-weight: 800; color: {text_color}; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05); user-select: all;">
                {digit}
            </div>
        </td>
        """)

    return f"""
    <table align="center" cellpadding="0" cellspacing="0" border="0" style="margin: 0 auto; white-space: nowrap !important;">
        <tr style="white-space: nowrap !important;">
            {''.join(cells)}
        </tr>
    </table>
    """


def send_signup_otp_email(user_email: str, otp_code: str, first_name: str = 'User', valid_minutes: int = 3, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional verification email containing the 6-digit OTP in single-line cards for account registration."""
    subject = f"🔐 {otp_code} is your DataNova Verification Code"
    boxes_html = _format_otp_boxes_html(otp_code, border_color="#6366F1", text_color="#312E81")

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{first_name or 'there'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 24px; line-height: 1.6;">
        Thank you for choosing <strong>DataNova Smart Analytics Platform</strong>. To complete your account registration and verify your email address, please enter the 6-digit one-time passcode below:
    </p>

    <!-- OTP Code Display Card -->
    <div style="text-align: center; margin: 26px 0; background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%); border: 2px dashed #6366f1; border-radius: 12px; padding: 24px 16px;">
        <div style="font-size: 11px; font-weight: 700; color: #6366f1; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 14px;">
            Your One-Time Passcode (OTP)
        </div>
        <div style="white-space: nowrap !important; overflow-x: auto; text-align: center; padding: 4px 0;">
            {boxes_html}
        </div>
        <div style="font-size: 12px; color: #64748b; margin-top: 14px; font-weight: 600;">
            ⏱️ Valid for <strong>{valid_minutes} minutes</strong> &bull; One-time use only
        </div>
    </div>

    <!-- Security Precaution Box -->
    <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; border-radius: 6px; padding: 14px 16px; margin: 22px 0;">
        <div style="color: #92400e; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">
            🛡️ Security Precaution
        </div>
        <p style="color: #78350f; font-size: 12px; margin: 0; line-height: 1.5;">
            Never share this OTP with anyone. DataNova representatives will never ask for your verification code. If you did not attempt to register on DataNova, please disregard this email.
        </p>
    </div>

    <!-- Details Table -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
        <table width="100%" cellpadding="4" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">Recipient Email:</td>
                <td style="color: #1e293b; font-weight: 600;">{user_email}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Verification Action:</td>
                <td style="color: #1e293b;">New Account Registration</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Dispatch Timestamp:</td>
                <td style="color: #1e293b;">{datetime.now().strftime('%B %d, %Y, %I:%M %p')}</td>
            </tr>
        </table>
    </div>
    """

    body_text = f"Hello {first_name},\n\nYour DataNova verification code is: {otp_code}\n\nThis code is valid for {valid_minutes} minutes. Never share this code with anyone.\n\nIf you did not request this, please ignore this email."
    body_html = _build_master_email(
        badge_text="Email Verification",
        badge_bg="#6366F1",
        header_title="Verify Your Email Address",
        header_subtitle="Enter the verification code to activate your DataNova account.",
        content_html=content_html,
        footer_note="Automated account security dispatch &bull; DataNova Smart Analytics Platform"
    )

    send_email_async(user_email, subject, body_text, body_html)


def send_forgot_password_otp_email(user_email: str, otp_code: str, first_name: str = 'User', valid_minutes: int = 3, ip_address: str = '127.0.0.1', device_info: str = 'Web Browser', base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional password reset OTP verification email with single-line cards."""
    subject = f"🔒 {otp_code} is your DataNova Password Reset Code"
    boxes_html = _format_otp_boxes_html(otp_code, border_color="#F97316", text_color="#9A3412")

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{first_name or 'User'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 24px; line-height: 1.6;">
        We received a request to reset the password for your <strong>DataNova</strong> account (<strong>{user_email}</strong>). Please use the 6-digit one-time passcode below to authorize your password update:
    </p>

    <!-- OTP Code Display Card -->
    <div style="text-align: center; margin: 26px 0; background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%); border: 2px dashed #f97316; border-radius: 12px; padding: 24px 16px;">
        <div style="font-size: 11px; font-weight: 700; color: #ea580c; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 14px;">
            Password Reset Verification Code
        </div>
        <div style="white-space: nowrap !important; overflow-x: auto; text-align: center; padding: 4px 0;">
            {boxes_html}
        </div>
        <div style="font-size: 12px; color: #7c2d12; margin-top: 14px; font-weight: 600;">
            ⏱️ Valid for <strong>{valid_minutes} minutes</strong> &bull; Expires if unused
        </div>
    </div>

    <!-- Request Metadata Table -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Request Metadata</div>
        <table width="100%" cellpadding="4" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">🕒 Request Time:</td>
                <td style="color: #1e293b;">{datetime.now().strftime('%B %d, %Y, %I:%M %p')}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">💻 Device / Browser:</td>
                <td style="color: #1e293b;">{device_info}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">🌐 IP Address:</td>
                <td style="color: #1e293b; font-family: monospace;">{ip_address}</td>
            </tr>
        </table>
    </div>

    <!-- Security Warning Box -->
    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #ef4444; border-radius: 6px; padding: 14px 16px; margin: 22px 0;">
        <div style="color: #991b1b; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">
            Did not request a password reset?
        </div>
        <p style="color: #7f1d1d; font-size: 12px; margin: 0; line-height: 1.5;">
            If you did not initiate this request, your account may be targeted. Your password has <strong>not</strong> been changed yet. Please ignore this email or notify your system administrator immediately.
        </p>
    </div>
    """

    body_text = f"Hello {first_name},\n\nYour DataNova password reset code is: {otp_code}\nValid for {valid_minutes} minutes.\n\nRequested from: {device_info} ({ip_address})\n\nIf you did not request this, please ignore this email."
    body_html = _build_master_email(
        badge_text="Security Reset",
        badge_bg="#EA580C",
        header_title="Password Reset Verification",
        header_subtitle="Authorize password update with your temporary verification code.",
        content_html=content_html,
        footer_note="Automated security service &bull; DataNova Smart Analytics Platform"
    )

    send_email_async(user_email, subject, body_text, body_html)


def send_password_reset_success_email(
    user_email: str,
    first_name: str = 'User',
    ip_address: str = '127.0.0.1',
    device_info: str = 'Web Browser',
    location: str = 'Secure Corporate Network',
    base_url: str = 'http://127.0.0.1:5000'
):
    """Sends a professional security alert confirming that password has been reset successfully, detailing browser, time, and admin contact."""
    subject = "🛡️ Password Changed Successfully - DataNova Security Alert"
    reset_time = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')

    # Security mailto link for immediate administrator reporting
    admin_mailto = f"mailto:admin@datanova.com?subject=URGENT:%20Unauthorized%20Password%20Change%20Alert%20({user_email})&body=Hello%20DataNova%20Administrator,%0A%0AI%20received%20a%20notification%20that%20the%20password%20for%20my%20DataNova%20account%20({user_email})%20was%20changed%20on%20{reset_time},%20but%20I%20did%20NOT%20authorize%20or%20perform%20this%20change.%0A%0APlease%20freeze%20my%20account%20immediately%20and%20investigate.%0A%0AAccount%20Email:%20{user_email}%0AReported%20Device:%20{device_info}%0AReported%20IP:%20{ip_address}%0A%0AThank%20you."

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{first_name or 'User'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 20px; line-height: 1.6;">
        This security advisory confirms that the password for your <strong>DataNova Smart Analytics Platform</strong> account (<strong>{user_email}</strong>) was successfully updated.
    </p>

    <!-- Success Confirmation Banner -->
    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981; border-radius: 8px; padding: 14px 18px; margin: 20px 0;">
        <div style="color: #166534; font-size: 13px; font-weight: 700; margin-bottom: 4px; display: flex; align-items: center;">
            <span style="font-size: 16px; margin-right: 6px;">✅</span> Password Change Successful
        </div>
        <p style="color: #14532d; font-size: 12px; margin: 0; line-height: 1.5;">
            Your credentials were confirmed via verified OTP. Any existing login sessions have been invalidated and you may now sign in using your new password.
        </p>
    </div>

    <!-- Security Activity Details Table -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 22px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
            Security Event Details
        </div>
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">💻 Browser &amp; Client:</td>
                <td style="color: #0f172a; font-weight: 700;">{device_info}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">🕒 Exact Timestamp:</td>
                <td style="color: #1e293b; font-weight: 600;">{reset_time}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">🌐 IP Address:</td>
                <td style="color: #1e293b; font-family: monospace;">{ip_address}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">📍 Network Location:</td>
                <td style="color: #1e293b;">{location}</td>
            </tr>
        </table>
    </div>

    <!-- Prominent Critical Warning Callout Box -->
    <div style="background-color: #fef2f2; border: 1.5px solid #f87171; border-left: 5px solid #dc2626; border-radius: 8px; padding: 18px 20px; margin: 24px 0;">
        <div style="color: #991b1b; font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">
            ⚠️ Critical Security Notice: Did you not change your password?
        </div>
        <p style="color: #7f1d1d; font-size: 13px; margin: 0 0 14px 0; line-height: 1.6;">
            If you did not perform or authorize this password update, someone else may have gained unauthorized access to your DataNova account. 
            <strong>Please contact the platform administrator immediately</strong> to lock your account and secure your organization's analytics.
        </p>
        <div>
            <a href="{admin_mailto}" style="display: inline-block; background-color: #dc2626; color: #ffffff; text-decoration: none; font-size: 12px; font-weight: 700; padding: 10px 20px; border-radius: 6px; box-shadow: 0 2px 4px rgba(220, 38, 38, 0.25);">
                🚨 Contact Administrator Immediately &rarr;
            </a>
        </div>
    </div>
    """

    body_text = f"Hello {first_name},\n\nYour DataNova account ({user_email}) password was successfully changed on {reset_time}.\n\nBrowser & Client: {device_info}\nIP Address: {ip_address}\nLocation: {location}\n\nIMPORTANT: If you did not make this change, please contact your administrator immediately at admin@datanova.com to secure your account.\n\nLog in: {base_url}/login"
    body_html = _build_master_email(
        badge_text="Password Changed",
        badge_bg="#10B981",
        header_title="Password Successfully Updated",
        header_subtitle="Your account credentials have been securely updated.",
        content_html=content_html,
        cta_text="Log In to DataNova",
        cta_url=f"{base_url}/login",
        footer_note="If you did not perform this change, please contact the platform administrator immediately."
    )

    send_email_async(user_email, subject, body_text, body_html)


def send_login_alert_email(user_email: str, first_name: str = 'User', login_time: str = None, ip_address: str = '127.0.0.1', device_info: str = None, location: str = "Local Network", user_agent: str = None, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional security login alert with location, browser, and security recovery actions."""
    if not device_info:
        dev_str, ip_str, loc_str = parse_client_device(user_agent=user_agent or '', ip_address=ip_address)
        device_info = dev_str
        if not location or location == "Local Network":
            location = loc_str
    if not login_time:
        login_time = datetime.now().strftime('%B %d, %Y, %I:%M %p')

    subject = f"🛡️ Security Alert: New Sign-in to Your DataNova Account ({device_info})"

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{first_name or 'User'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 20px;">
        We noticed a new sign-in to your <strong>DataNova</strong> account. Please review the activity details below to verify it was you:
    </p>

    <!-- Sign-in Details Table -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">🕒 Timestamp:</td>
                <td style="color: #1e293b; font-weight: 600;">{login_time}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">💻 Device / Browser:</td>
                <td style="color: #1e293b; font-weight: 600;">{device_info}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">🌐 IP Address:</td>
                <td style="color: #1e293b; font-family: monospace;">{ip_address}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">📍 Location:</td>
                <td style="color: #1e293b;">{location}</td>
            </tr>
        </table>
    </div>

    <!-- Security Warning Card -->
    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-left: 4px solid #ef4444; border-radius: 6px; padding: 14px 16px; margin: 20px 0;">
        <div style="color: #991b1b; font-size: 13px; font-weight: 700; margin-bottom: 4px;">
            Did not recognize this activity?
        </div>
        <p style="color: #7f1d1d; font-size: 12px; margin: 0; line-height: 1.5;">
            If you did not initiate this sign-in, your account credentials may be compromised. We strongly recommend that you change your password immediately and notify the system administrator to safeguard your analytical assets.
        </p>
    </div>
    """

    body_text = f"Hello {first_name},\n\nSecurity Alert: New Sign-in to your DataNova account.\nTime: {login_time}\nDevice: {device_info}\nIP: {ip_address}\nLocation: {location}\n\nIf this wasn't you, secure your account immediately: {base_url}/login"
    body_html = _build_master_email(
        badge_text="Security Alert",
        badge_bg="#EF4444",
        header_title="New Account Sign-in",
        header_subtitle="Review recent authentication activity on your DataNova account.",
        content_html=content_html,
        cta_text="Secure Account & Change Password",
        cta_url=f"{base_url}/login",
        secondary_text="Report unauthorized access to System Administrator",
        secondary_url=f"mailto:support@datanova.com?subject=Unauthorized%20Login%20Alert%20({user_email})",
        footer_note="You received this mandatory security alert because your DataNova account was accessed from a new session."
    )

    send_email_async(user_email, subject, body_text, body_html)


def send_contact_admin_email(admin_emails: List[str], user_name: str, user_email: str, user_role: str, subject: str, category: str, message: str, attachment_url: Optional[str] = None, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional notification to platform administrators when a user contacts admin."""
    if not admin_emails:
        return

    mail_subject = f"📩 [Support Ticket] {subject} (from {user_name})"
    attach_html = f"""
    <div style="margin-top: 12px; padding: 10px; background-color: #f1f5f9; border-radius: 6px; font-size: 12px;">
        <strong>Attached File / Screenshot:</strong> <a href="{base_url}{attachment_url}" target="_blank" style="color: #2563eb; text-decoration: underline;">View Attachment</a>
    </div>
    """ if attachment_url else ""

    content_html = f"""
    <p style="font-size: 14px; color: #1e293b; margin-top: 0;">
        A platform user has submitted a support inquiry from their dashboard:
    </p>

    <!-- Ticket Summary -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="5" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 130px; font-weight: 600;">Submitted By:</td>
                <td style="color: #1e293b; font-weight: 600;">{user_name} &lt;{user_email}&gt;</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">User Role:</td>
                <td><span style="background-color: #e2e8f0; color: #334155; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: capitalize;">{user_role}</span></td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Inquiry Category:</td>
                <td style="color: #1e293b; font-weight: 600;">{category}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Subject:</td>
                <td style="color: #0f172a; font-weight: 700;">{subject}</td>
            </tr>
        </table>
    </div>

    <div style="background-color: #ffffff; border: 1px solid #cbd5e1; border-left: 4px solid #4F46E5; border-radius: 6px; padding: 16px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 6px;">Message Content</div>
        <div style="color: #1e293b; font-size: 13px; line-height: 1.6; white-space: pre-wrap;">{message}</div>
        {attach_html}
    </div>
    """

    body_text = f"New Support Ticket:\nFrom: {user_name} ({user_email})\nRole: {user_role}\nCategory: {category}\nSubject: {subject}\n\nMessage:\n{message}\n\nAdmin Portal: {base_url}/dashboard/admin#adminSupportSection"
    body_html = _build_master_email(
        badge_text="Support Ticket",
        badge_bg="#6366F1",
        header_title="Inbound User Inquiry",
        header_subtitle="Action requested by a registered platform user.",
        content_html=content_html,
        cta_text="Manage Tickets in Admin Portal",
        cta_url=f"{base_url}/dashboard/admin#adminSupportSection",
        footer_note="This notification was routed directly to all active System Administrators."
    )

    for admin_email in admin_emails:
        if admin_email and '@' in admin_email:
            send_email_async(admin_email, mail_subject, body_text, body_html)


def send_issue_resolved_email(user_email: str, user_name: str, subject: str, category: str, resolution_notes: str = None, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional notification to user when their inquiry is marked Resolved by Admin."""
    mail_subject = f"✅ Issue Resolved: {subject}"
    notes_html = f"""
    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981; border-radius: 6px; padding: 14px 16px; margin: 18px 0;">
        <div style="color: #166534; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">Resolution Summary</div>
        <p style="color: #14532d; font-size: 13px; margin: 0; line-height: 1.5;">
            {resolution_notes or 'Your inquiry has been investigated, resolved, and closed by the DataNova Administration Team.'}
        </p>
    </div>
    """

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{user_name or 'User'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 18px;">
        Good news! Your support inquiry regarding <strong>"{subject}"</strong> has been investigated and marked as <strong style="color: #16a34a;">Resolved</strong> by the DataNova Administration Team.
    </p>

    <!-- Ticket Summary Card -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="5" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 130px; font-weight: 600;">Inquiry Subject:</td>
                <td style="color: #1e293b; font-weight: 700;">{subject}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Category:</td>
                <td style="color: #1e293b;">{category}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Status:</td>
                <td><span style="background-color: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 4px;">Resolved</span></td>
            </tr>
        </table>
    </div>

    {notes_html}

    <p style="color: #475569; font-size: 13px;">
        If you continue to experience difficulties or have further questions, please do not hesitate to contact our team again from your dashboard.
    </p>
    """

    body_text = f"Hello {user_name},\n\nYour support inquiry '{subject}' has been marked as Resolved by the DataNova administration team.\n\nVisit your dashboard: {base_url}/login"
    body_html = _build_master_email(
        badge_text="Issue Resolved",
        badge_bg="#10B981",
        header_title="Support Ticket Closed",
        header_subtitle="Your issue has been resolved by our platform operations team.",
        content_html=content_html,
        cta_text="Return to Your Dashboard",
        cta_url=f"{base_url}/login",
        footer_note="Thank you for partnering with DataNova Smart Analytics Platform."
    )

    send_email_async(user_email, mail_subject, body_text, body_html)


def send_task_assigned_email(assignee_email: str, assignee_name: str, manager_name: str, manager_email: str, task_title: str, priority: str = 'Medium', due_date: str = None, description: str = '', dataset_name: str = None, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional notification to team member when assigned a task by their manager."""
    subject = f"📋 New Task Assigned: {task_title}"
    priority_col = "#ef4444" if priority.lower() in ('urgent', 'high') else ("#f59e0b" if priority.lower() == 'medium' else "#3b82f6")

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{assignee_name or 'Team Member'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 18px;">
        <strong>{manager_name}</strong> has assigned a new task to your queue on DataNova:
    </p>

    <!-- Task Spec Table -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">Task Title:</td>
                <td style="color: #0f172a; font-weight: 700; font-size: 14px;">{task_title}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Priority:</td>
                <td><span style="color: {priority_col}; font-weight: 700;">{priority}</span></td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Due Date:</td>
                <td style="color: #1e293b;">{due_date or 'No deadline specified'}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Assigned By:</td>
                <td style="color: #1e293b;">{manager_name} ({manager_email})</td>
            </tr>
            {f'<tr><td style="color: #64748b; font-weight: 600;">Attached Dataset:</td><td style="color: #2563eb; font-weight: 600;">{dataset_name}</td></tr>' if dataset_name else ''}
        </table>
    </div>

    <div style="background-color: #ffffff; border: 1px solid #cbd5e1; border-left: 4px solid #6366f1; border-radius: 6px; padding: 14px 16px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Task Description &amp; Instructions</div>
        <p style="color: #1e293b; font-size: 13px; margin: 0; line-height: 1.6; white-space: pre-wrap;">{description or 'Please review the assigned analytical task and submit results in your dashboard.'}</p>
    </div>
    """

    body_text = f"Hello {assignee_name},\n\nYou have been assigned a new task: '{task_title}' by {manager_name}.\nPriority: {priority}\nDue Date: {due_date or 'None'}\n\nPlease view your dashboard: {base_url}/login"
    body_html = _build_master_email(
        badge_text="Task Assignment",
        badge_bg="#6366F1",
        header_title="New Task Assignment",
        header_subtitle=f"Assigned by Manager {manager_name}",
        content_html=content_html,
        cta_text="View & Work on Task",
        cta_url=f"{base_url}/login",
        footer_note="Automated task dispatch by DataNova Manager Operations."
    )

    send_email_async(assignee_email, subject, body_text, body_html)


def send_task_completed_email(manager_email: str, manager_name: str, assignee_name: str, assignee_email: str, task_title: str, remark: str = None, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional notification to manager when team member completes a task."""
    subject = f"✅ Task Completed: {task_title} (by {assignee_name})"

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{manager_name or 'Manager'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 18px;">
        Team member <strong>{assignee_name}</strong> has successfully completed and submitted the assigned task for your review.
    </p>

    <!-- Task Completion Card -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">Task Title:</td>
                <td style="color: #0f172a; font-weight: 700; font-size: 14px;">{task_title}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Completed By:</td>
                <td style="color: #1e293b; font-weight: 600;">{assignee_name} &lt;{assignee_email}&gt;</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Status:</td>
                <td><span style="background-color: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 4px;">Completed &bull; Ready for Review</span></td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Submission Time:</td>
                <td style="color: #1e293b;">{datetime.now().strftime('%B %d, %Y, %I:%M %p')}</td>
            </tr>
        </table>
    </div>

    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981; border-radius: 6px; padding: 14px 16px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase; margin-bottom: 4px;">Member's Completion Remark</div>
        <p style="color: #14532d; font-size: 13px; margin: 0; line-height: 1.5; white-space: pre-wrap;">{remark or 'Task finished successfully and ready for approval.'}</p>
    </div>
    """

    body_text = f"Hello {manager_name},\n\nTask '{task_title}' has been completed by {assignee_name}.\nRemark: {remark or 'None'}\n\nReview in manager dashboard: {base_url}/login"
    body_html = _build_master_email(
        badge_text="Task Completed",
        badge_bg="#10B981",
        header_title="Task Submission Received",
        header_subtitle=f"Submitted by {assignee_name}",
        content_html=content_html,
        cta_text="Review & Approve in Manager Portal",
        cta_url=f"{base_url}/login",
        footer_note="Automated task tracking & lifecycle notification."
    )

    send_email_async(manager_email, subject, body_text, body_html)


def send_task_completed_and_dashboard_shared_email(
    manager_email: str,
    manager_name: str,
    assignee_name: str,
    assignee_email: str,
    assignee_role: str = 'Analyst',
    task_title: str = 'Assigned Task',
    dashboard_title: str = 'Completed Analysis',
    dataset_name: str = 'Dataset',
    row_count: int = 0,
    col_count: int = 0,
    remark: Optional[str] = None,
    base_url: str = 'http://127.0.0.1:5000'
):
    """Sends a professional executive notification to the manager when a team member completes a task and shares the dashboard."""
    subject = f"📋 Task Completed & Dashboard Shared: {task_title} (by {assignee_name})"
    sub_time = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')

    data_meta = f"{dataset_name}"
    if row_count or col_count:
        data_meta += f" ({row_count:,} rows &bull; {col_count} columns)"

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{manager_name or 'Manager'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 20px; line-height: 1.6;">
        Team member <strong>{assignee_name}</strong> has successfully completed the assigned task <strong>"{task_title}"</strong> and shared the finalized analytical dashboard with you for review.
    </p>

    <!-- Task & Shared Dashboard Metadata Card -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px;">
            Submission &amp; Dashboard Overview
        </div>
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 145px; font-weight: 600;">📋 Task Title:</td>
                <td style="color: #0f172a; font-weight: 700; font-size: 14px;">{task_title}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">📊 Shared Dashboard:</td>
                <td style="color: #4338ca; font-weight: 700;">{dashboard_title}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">📁 Dataset:</td>
                <td style="color: #1e293b;">{data_meta}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">👤 Completed By:</td>
                <td style="color: #1e293b;"><strong>{assignee_name}</strong> &lt;{assignee_email}&gt; ({assignee_role})</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">🕒 Submission Time:</td>
                <td style="color: #1e293b;">{sub_time}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">⚡ Status:</td>
                <td><span style="background-color: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 4px;">Completed &bull; Shared for Review</span></td>
            </tr>
        </table>
    </div>

    <!-- Member's Submission Remarks / Findings -->
    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981; border-radius: 6px; padding: 16px 18px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase; margin-bottom: 6px;">
            Team Member's Remarks &amp; Analysis Summary
        </div>
        <p style="color: #14532d; font-size: 13px; margin: 0; line-height: 1.6; white-space: pre-wrap;">{remark or 'Analysis completed and dashboard published to manager.'}</p>
    </div>
    """

    body_text = f"Hello {manager_name},\n\nTeam member {assignee_name} ({assignee_email}) has completed the task: '{task_title}' and shared the dashboard: '{dashboard_title}'.\nDataset: {data_meta}\nSubmitted: {sub_time}\nRemark: {remark or 'None'}\n\nReview in manager portal: {base_url}/dashboard/manager#sharedDashboardsSection"
    body_html = _build_master_email(
        badge_text="Task Completed & Shared",
        badge_bg="#10B981",
        header_title="Task Completed & Dashboard Shared",
        header_subtitle=f"Analytical submission from {assignee_name} is ready for review.",
        content_html=content_html,
        cta_text="Review Dashboard in Manager Portal",
        cta_url=f"{base_url}/dashboard/manager#sharedDashboardsSection",
        secondary_text="Or log in to your DataNova workspace",
        secondary_url=f"{base_url}/login",
        footer_note="Automated task tracking & collaboration service &bull; DataNova Platform"
    )

    send_email_async(manager_email, subject, body_text, body_html)


def send_dashboard_shared_with_manager_email(
    manager_email: str,
    manager_name: str,
    sharer_name: str,
    sharer_email: str,
    sharer_role: str = 'Team Member',
    dashboard_title: str = 'Analytical Dashboard',
    dataset_name: str = 'Dataset',
    description: Optional[str] = None,
    base_url: str = 'http://127.0.0.1:5000'
):
    """Sends a professional notification to manager when a team member shares a dashboard with them."""
    subject = f"📊 Dashboard Shared with You: {dashboard_title} (by {sharer_name})"
    share_time = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{manager_name or 'Manager'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 20px; line-height: 1.6;">
        Team member <strong>{sharer_name}</strong> ({sharer_role}) has shared an analytical dashboard with you on <strong>DataNova</strong>.
    </p>

    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">📊 Dashboard Title:</td>
                <td style="color: #4338ca; font-weight: 700; font-size: 14px;">{dashboard_title}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">📁 Dataset:</td>
                <td style="color: #1e293b;">{dataset_name}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">👤 Shared By:</td>
                <td style="color: #1e293b;">{sharer_name} &lt;{sharer_email}&gt;</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">🕒 Shared Time:</td>
                <td style="color: #1e293b;">{share_time}</td>
            </tr>
        </table>
    </div>

    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #10b981; border-radius: 6px; padding: 14px 16px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase; margin-bottom: 4px;">Notes &amp; Description</div>
        <p style="color: #14532d; font-size: 13px; margin: 0; line-height: 1.5; white-space: pre-wrap;">{description or 'Dashboard shared for review and team collaboration.'}</p>
    </div>
    """

    body_text = f"Hello {manager_name},\n\n{sharer_name} has shared a dashboard '{dashboard_title}' with you.\nDataset: {dataset_name}\nNotes: {description or 'None'}\n\nView in manager portal: {base_url}/dashboard/manager#sharedDashboardsSection"
    body_html = _build_master_email(
        badge_text="Dashboard Shared",
        badge_bg="#6366F1",
        header_title="New Dashboard Shared",
        header_subtitle=f"Shared by {sharer_name}",
        content_html=content_html,
        cta_text="Open Dashboard in Manager Portal",
        cta_url=f"{base_url}/dashboard/manager#sharedDashboardsSection",
        footer_note="Automated team sharing notification &bull; DataNova Platform"
    )

    send_email_async(manager_email, subject, body_text, body_html)


def send_task_review_status_email(assignee_email: str, assignee_name: str, manager_name: str, task_title: str, new_status: str, remark: str = None, base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional notification when manager Approves or Reopens a task."""
    is_approved = new_status.lower() in ('approved', 'accepted')
    badge_bg = "#10B981" if is_approved else "#F59E0B"
    badge_txt = "Task Approved" if is_approved else "Task Reopened"
    subject = f"{'🎉 Task Approved' if is_approved else '🔄 Task Reopened'}: {task_title}"

    status_tag = '<span style="background-color: #dcfce7; color: #15803d; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 4px;">Approved</span>' if is_approved else '<span style="background-color: #fef3c7; color: #b45309; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 4px;">Reopened / Revisions Requested</span>'

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{assignee_name or 'Team Member'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 18px;">
        Your manager <strong>{manager_name}</strong> has reviewed your task submission for <strong>"{task_title}"</strong>.
    </p>

    <!-- Review Status Card -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">Task Title:</td>
                <td style="color: #0f172a; font-weight: 700; font-size: 14px;">{task_title}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Review Outcome:</td>
                <td>{status_tag}</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Reviewed By:</td>
                <td style="color: #1e293b;">{manager_name}</td>
            </tr>
        </table>
    </div>

    <div style="background-color: {'#f0fdf4' if is_approved else '#fffbeb'}; border: 1px solid {'#bbf7d0' if is_approved else '#fde68a'}; border-left: 4px solid {'#10b981' if is_approved else '#f59e0b'}; border-radius: 6px; padding: 14px 16px; margin: 18px 0;">
        <div style="font-size: 11px; font-weight: 700; color: {'#166534' if is_approved else '#92400e'}; text-transform: uppercase; margin-bottom: 4px;">Manager Feedback &amp; Remarks</div>
        <p style="color: {'#14532d' if is_approved else '#78350f'}; font-size: 13px; margin: 0; line-height: 1.5; white-space: pre-wrap;">
            {remark or ('Congratulations! Your deliverables have been reviewed and approved.' if is_approved else 'Please review the manager notes and resubmit upon completion.')}
        </p>
    </div>
    """

    body_text = f"Hello {assignee_name},\n\nYour task '{task_title}' status has been updated to: {new_status} by {manager_name}.\nFeedback: {remark or 'None'}\n\nView dashboard: {base_url}/login"
    body_html = _build_master_email(
        badge_text=badge_txt,
        badge_bg=badge_bg,
        header_title="Task Review Decision",
        header_subtitle=f"Status: {new_status} by {manager_name}",
        content_html=content_html,
        cta_text="Open Task in Dashboard",
        cta_url=f"{base_url}/login",
        footer_note="DataNova Team Workflows & Project Governance."
    )

    send_email_async(assignee_email, subject, body_text, body_html)


def send_api_quota_exhausted_email(dev_email: str, dev_name: str, key_name: str = "Primary API Key", key_prefix: str = "dn_live", monthly_limit: int = 2000, reset_date: str = "the 1st of next month", base_url: str = 'http://127.0.0.1:5000'):
    """Sends a professional notification to developer when their monthly API quota is exhausted."""
    subject = f"⚠️ Alert: Your DataNova API Monthly Quota Has Been Exhausted ({key_name})"

    content_html = f"""
    <p style="font-size: 15px; color: #1e293b; margin-top: 0;">
        Hello <strong>{dev_name or 'Developer'}</strong>,
    </p>
    <p style="color: #475569; margin-bottom: 18px;">
        Your DataNova API monthly request quota of <strong>{monthly_limit:,} requests</strong> has reached 100% capacity. Any subsequent calls with this API key will return <code style="background-color: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 4px;">HTTP 429 Too Many Requests</code>.
    </p>

    <!-- Quota Metrics Table -->
    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; margin: 18px 0;">
        <table width="100%" cellpadding="6" cellspacing="0" border="0" style="font-size: 13px;">
            <tr>
                <td style="color: #64748b; width: 140px; font-weight: 600;">API Key Identifier:</td>
                <td style="color: #0f172a; font-weight: 700; font-family: monospace;">{key_name} ({key_prefix}••••••••)</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Monthly Allowance:</td>
                <td style="color: #1e293b; font-weight: 600;">{monthly_limit:,} requests</td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Current Usage:</td>
                <td><span style="color: #dc2626; font-weight: 700;">{monthly_limit:,} / {monthly_limit:,} (100% Exhausted)</span></td>
            </tr>
            <tr>
                <td style="color: #64748b; font-weight: 600;">Next Automatic Reset:</td>
                <td style="color: #2563eb; font-weight: 600;">{reset_date}</td>
            </tr>
        </table>
    </div>

    <!-- Recommendations Card -->
    <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-left: 4px solid #f59e0b; border-radius: 6px; padding: 14px 16px; margin: 18px 0;">
        <div style="color: #92400e; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px;">How to Restore API Ingestion</div>
        <ul style="color: #78350f; font-size: 12px; margin: 0; padding-left: 18px; line-height: 1.6;">
            <li><strong>Automatic Reset:</strong> Your quota will automatically restore on {reset_date}.</li>
            <li><strong>Quota Increase / Tier Upgrade:</strong> Contact your system administrator to increase your monthly limit.</li>
            <li><strong>Optimize Queries:</strong> Leverage pagination, limit queries, and cache EDA payloads.</li>
        </ul>
    </div>
    """

    body_text = f"Hello {dev_name},\n\nYour DataNova API monthly quota of {monthly_limit:,} requests has been exhausted.\nNext reset date: {reset_date}.\n\nView usage telemetry: {base_url}/developer"
    body_html = _build_master_email(
        badge_text="Quota Exhausted",
        badge_bg="#DC2626",
        header_title="API Rate Limit Warning",
        header_subtitle=f"Monthly ceiling reached for key {key_name}",
        content_html=content_html,
        cta_text="View Developer Analytics Console",
        cta_url=f"{base_url}/developer",
        secondary_text="Request Quota Upgrade from Support",
        secondary_url=f"mailto:support@datanova.com?subject=Quota%20Upgrade%20Request%20({dev_email})",
        footer_note="Developer API Rate Limiting & Telemetry Governance &bull; DataNova"
    )

    send_email_async(dev_email, subject, body_text, body_html)


def test_smtp_connection(to_email: str, custom_settings: dict = None) -> tuple:
    """Tests SMTP configuration by attempting a connection and sending a verification email."""
    subject = "DataNova — SMTP Configuration Verification"
    body_text = "Hello,\n\nThis is a verification email from DataNova Smart Analytics Platform. Your SMTP settings have been validated successfully."
    body_html = _build_master_email(
        badge_text="System Verified",
        badge_bg="#10B981",
        header_title="SMTP Service Verified",
        header_subtitle="Outbound email communication test completed successfully.",
        content_html="""
        <p style="font-size: 14px; color: #1e293b; margin-top: 0;">
            Your DataNova SMTP email infrastructure has been <strong>successfully tested and verified</strong>.
        </p>
        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin: 15px 0; font-size: 13px;">
            <div style="margin-bottom: 4px;"><strong>Service Status:</strong> <span style="color: #16a34a; font-weight: 700;">Online &amp; Connected</span></div>
            <div><strong>Verification Timestamp:</strong> Generated by System Administrator</div>
        </div>
        """,
        footer_note="DataNova Smart Analytics Platform &bull; Automated System Verification"
    )
    return send_smtp_email(to_email, subject, body_text, body_html, override_settings=custom_settings)
