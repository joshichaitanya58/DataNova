"""
DataNova OTP Service (100% Session-Based with 3-Minute Validity)
Handles cryptographically secure 6-digit OTP generation, session-state verification,
rate-limiting cooldowns, max attempt protection, and notification dispatch.
NO database table or records are used for OTP storage (session-only).
"""

import time
import secrets
import logging
from datetime import datetime
from typing import Tuple, Dict, Any, Optional
from flask import current_app, session
import pymysql

from database.db_connector import get_db_connection
from . import email_service
from .. import bcrypt

logger = logging.getLogger(__name__)

OTP_EXPIRY_MINUTES = 3          # Exact 3-minute validity as requested
OTP_EXPIRY_SECONDS = 180        # 180 seconds
RESEND_COOLDOWN_SECONDS = 30    # 30-second rate-limit between resends
MAX_VERIFICATION_ATTEMPTS = 5   # Max 5 incorrect attempts before lockout


def generate_otp() -> str:
    """Generates a cryptographically secure 6-digit numerical OTP."""
    return f"{secrets.randbelow(900000) + 100000}"


# =====================================================================
# Account Signup Flow (Session-Based OTP)
# =====================================================================

def create_signup_otp(
    first_name: str,
    last_name: str,
    email: str,
    password: str,
    role: str,
    organization: Optional[str] = None,
    phone: Optional[str] = None,
    allowed_roles: Optional[list] = None,
    base_url: str = 'http://127.0.0.1:5000'
) -> Tuple[bool, str, int]:
    """
    Validates signup details, checks for duplicate email, hashes password,
    stores registration payload & OTP in Flask session (3 min validity),
    and sends an executive verification email. Zero database OTP writes.
    Returns (success, message, http_status_code).
    """
    from ..auth import ALLOWED_ROLES
    if allowed_roles is None:
        allowed_roles = ALLOWED_ROLES

    first_name = (first_name or '').strip()
    last_name = (last_name or '').strip()
    email = (email or '').strip().lower()
    role_clean = (role or 'developer').strip().lower()
    org_clean = (organization or 'General').strip() or 'General'
    phone_clean = (phone or '').strip() or None

    if not all([first_name, last_name, email, password]):
        return False, "First name, last name, email, and password are required.", 400

    if role_clean not in allowed_roles:
        return False, "Invalid or unauthorized role requested.", 400

    if '@' not in email or '.' not in email or len(email) < 5:
        return False, "Please enter a valid email address.", 400

    if len(str(password)) < 6:
        return False, "Password must be at least 6 characters long.", 400

    try:
        settings = current_app.config.get('SYSTEM_SETTINGS', {}) if current_app else {}
    except Exception:
        settings = {}

    if settings.get('enforce_strong_passwords', True):
        pwd = str(password)
        if len(pwd) < 8 or not any(c.isupper() for c in pwd) or not any(c.isdigit() for c in pwd):
            return False, "Password must be at least 8 characters long and contain at least one uppercase letter and one number.", 400

    conn = get_db_connection()
    if not conn:
        return False, "Database connection error. Please try again later.", 500

    try:
        with conn.cursor() as cursor:
            # 1. Check if an account already exists with this email
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return False, "An account with this email address already exists. Please log in.", 400

            # 2. Safety Feature: Strictly only ONE Administrator is permitted on the platform
            if role_clean == 'admin':
                cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
                if cursor.fetchone():
                    return False, "An Administrator account is already registered on this platform. Only one Administrator is permitted for security reasons.", 403
    finally:
        conn.close()

    now_ts = time.time()

    # 2. Check for recent unverified OTP session to enforce resend cooldown
    last_sent = session.get('signup_otp_sent_at', 0)
    if (now_ts - last_sent) < RESEND_COOLDOWN_SECONDS:
        wait_sec = int(RESEND_COOLDOWN_SECONDS - (now_ts - last_sent))
        return False, f"Please wait {wait_sec} seconds before requesting a new verification code.", 429

    # 3. Securely hash password before storing in pending session payload
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    otp_code = generate_otp()

    # 4. Store in session (NO database table, zero DB storage)
    session['signup_pending'] = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'password': hashed_password,
        'role': role_clean,
        'organization': org_clean,
        'phone': phone_clean,
        'otp_code': otp_code,
        'expires_at': now_ts + OTP_EXPIRY_SECONDS,
        'attempts': 0
    }
    session['signup_otp_sent_at'] = now_ts
    session.modified = True

    # 5. Dispatch professional verification email (with 3-minute validity)
    logger.info(f"🔑 [DATANOVA OTP] Generated 6-digit signup OTP for {email}: {otp_code}")
    try:
        mail_ok, mail_err = email_service.send_signup_otp_email(
            user_email=email,
            otp_code=otp_code,
            first_name=first_name,
            valid_minutes=OTP_EXPIRY_MINUTES,
            base_url=base_url
        )
        if not mail_ok:
            session.pop('signup_pending', None)
            session.pop('signup_otp_sent_at', None)
            session.modified = True
            logger.error(f"Failed to deliver signup OTP email to {email}: {mail_err}")
            return False, f"Failed to deliver verification code email: {mail_err}", 500
    except Exception as mail_err:
        session.pop('signup_pending', None)
        session.pop('signup_otp_sent_at', None)
        session.modified = True
        logger.error(f"Failed to dispatch signup OTP email to {email}: {mail_err}")
        return False, f"Failed to deliver verification code email: {mail_err}", 500

    logger.info(f"Generated session-based signup OTP for {email} (valid 3 mins)")
    return True, "Verification code sent to your email address.", 200


def verify_signup_otp(
    email: str,
    otp_code: str,
    base_url: str = 'http://127.0.0.1:5000' or 'https://datanova-fude.onrender.com'
) -> Tuple[bool, str, int, Optional[Dict[str, Any]]]:
    """
    Verifies the OTP stored in session. If valid and within 3 minutes, completes user registration
    in MySQL database, clears session state, and dispatches onboarding welcome email.
    Returns (success, message, http_status_code, user_data).
    """
    email = (email or '').strip().lower()
    otp_code = (otp_code or '').strip()

    if not email or not otp_code:
        return False, "Email address and 6-digit verification code are required.", 400, None

    pending = session.get('signup_pending')
    if not pending or pending.get('email') != email:
        return False, "No active registration session found. Please submit the sign-up form.", 404, None

    now_ts = time.time()

    # 1. Check expiration (3 minutes)
    if now_ts > pending.get('expires_at', 0):
        session.pop('signup_pending', None)
        session.modified = True
        return False, "Verification code has expired (3 minutes validity). Please request a new code.", 400, None

    # 2. Check maximum attempts
    attempts = pending.get('attempts', 0)
    if attempts >= MAX_VERIFICATION_ATTEMPTS:
        session.pop('signup_pending', None)
        session.modified = True
        return False, "Maximum verification attempts exceeded. Please restart registration.", 429, None

    # 3. Check code match
    if str(pending.get('otp_code')) != str(otp_code):
        attempts += 1
        pending['attempts'] = attempts
        session['signup_pending'] = pending
        session.modified = True
        remaining = MAX_VERIFICATION_ATTEMPTS - attempts
        if remaining > 0:
            return False, f"Incorrect verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.", 400, None
        else:
            session.pop('signup_pending', None)
            session.modified = True
            return False, "Maximum verification attempts reached. Please restart registration.", 429, None

    # 4. Code verified! Create user in database
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error. Please try again later.", 500, None

    user_data = dict(pending)
    # Don't leak raw otp info
    user_data.pop('otp_code', None)
    user_data.pop('expires_at', None)
    user_data.pop('attempts', None)

    try:
        with conn.cursor() as cursor:
            # Check duplicate email once more before insert
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                session.pop('signup_pending', None)
                session.modified = True
                return False, "An account with this email address already exists. Please log in.", 400, None

            # Safety Feature: Strictly only ONE Administrator is permitted on the platform
            if user_data.get('role') == 'admin':
                cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
                if cursor.fetchone():
                    session.pop('signup_pending', None)
                    session.modified = True
                    return False, "An Administrator account is already registered on this platform. Only one Administrator is permitted for security reasons.", 403, None

            cursor.execute(
                """
                INSERT INTO users (first_name, last_name, email, password, role, organization, phone, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                """,
                (
                    user_data['first_name'],
                    user_data['last_name'],
                    user_data['email'],
                    user_data['password'],
                    user_data['role'],
                    (user_data.get('organization') or 'General').strip() or 'General',
                    user_data.get('phone')
                )
            )
            conn.commit()
            new_id = cursor.lastrowid
            user_data['id'] = new_id

        # 5. Clear session pending registration
        session.pop('signup_pending', None)
        session.pop('signup_otp_sent_at', None)
        session.modified = True

        # 6. Dispatch executive onboarding Welcome Email
        try:
            email_service.send_welcome_email(
                user_email=user_data['email'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                role=user_data['role'],
                organization=user_data.get('organization', 'General'),
                base_url=base_url
            )
        except Exception as welcome_err:
            logger.warning(f"Failed to dispatch welcome email: {welcome_err}")

        logger.info(f"Successfully verified signup OTP and created user account for {email}")
        return True, "Email verified successfully! Your account is ready.", 200, user_data

    except pymysql.IntegrityError:
        session.pop('signup_pending', None)
        session.modified = True
        return False, "An account with this email already exists.", 400, None
    except Exception as e:
        logger.error(f"Error creating user record for {email}: {e}")
        return False, f"Account creation failed: {str(e)}", 500, None
    finally:
        conn.close()


def resend_signup_otp(email: str, base_url: str = 'http://127.0.0.1:5000') -> Tuple[bool, str, int]:
    """Resends a fresh 3-minute OTP for an existing session with cooldown enforcement."""
    email = (email or '').strip().lower()
    if not email:
        return False, "Email address is required.", 400

    pending = session.get('signup_pending')
    if not pending or pending.get('email') != email:
        return False, "No active registration session found. Please submit the sign-up form.", 404

    now_ts = time.time()
    last_sent = session.get('signup_otp_sent_at', 0)
    if (now_ts - last_sent) < RESEND_COOLDOWN_SECONDS:
        wait_sec = int(RESEND_COOLDOWN_SECONDS - (now_ts - last_sent))
        return False, f"Please wait {wait_sec} seconds before requesting a new code.", 429

    new_otp = generate_otp()
    pending['otp_code'] = new_otp
    pending['expires_at'] = now_ts + OTP_EXPIRY_SECONDS
    pending['attempts'] = 0
    session['signup_pending'] = pending
    session['signup_otp_sent_at'] = now_ts
    session.modified = True

    first_name = pending.get('first_name', 'there')
    logger.info(f"🔑 [DATANOVA OTP] Resent 6-digit signup OTP for {email}: {new_otp}")
    mail_ok, mail_err = email_service.send_signup_otp_email(
        user_email=email,
        otp_code=new_otp,
        first_name=first_name,
        valid_minutes=OTP_EXPIRY_MINUTES,
        base_url=base_url
    )
    if not mail_ok:
        logger.error(f"Failed to resend signup OTP email to {email}: {mail_err}")
        return False, f"Failed to deliver verification code email: {mail_err}", 500

    return True, "A new verification code has been sent to your email address.", 200


# =====================================================================
# Forgot Password Flow (Session-Based OTP)
# =====================================================================

def create_forgot_password_otp(
    email: str,
    req=None,
    base_url: str = 'http://127.0.0.1:5000'
) -> Tuple[bool, str, int]:
    """
    Checks if account exists for email, generates a 6-digit password reset OTP,
    stores in session (3 min validity), and dispatches security verification email. Zero DB OTP writes.
    """
    email = (email or '').strip().lower()
    if not email:
        return False, "Email address is required.", 400

    conn = get_db_connection()
    if not conn:
        return False, "Database connection error. Please try again later.", 500

    try:
        with conn.cursor() as cursor:
            # 1. Verify user exists
            cursor.execute(
                "SELECT id, first_name, email FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()
            if not user:
                return False, "No account found with this email address. Please check your spelling or sign up.", 404
    finally:
        conn.close()

    now_ts = time.time()

    # 2. Check resend cooldown
    last_sent = session.get('forgot_otp_sent_at', 0)
    if (now_ts - last_sent) < RESEND_COOLDOWN_SECONDS:
        wait_sec = int(RESEND_COOLDOWN_SECONDS - (now_ts - last_sent))
        return False, f"Please wait {wait_sec} seconds before requesting a new code.", 429

    otp_code = generate_otp()

    # 3. Store in session (NO database table, zero DB storage)
    session['forgot_pending'] = {
        'email': email,
        'first_name': user.get('first_name', 'User'),
        'otp_code': otp_code,
        'expires_at': now_ts + OTP_EXPIRY_SECONDS,
        'attempts': 0
    }
    session['forgot_otp_sent_at'] = now_ts
    session.modified = True

    # 4. Parse client device details for the security email
    device_str, client_ip, _ = email_service.parse_client_device(req)

    # 5. Dispatch professional password reset OTP email
    logger.info(f"🔑 [DATANOVA OTP] Generated password reset OTP for {email}: {otp_code}")
    mail_ok, mail_err = email_service.send_forgot_password_otp_email(
        user_email=email,
        otp_code=otp_code,
        first_name=user.get('first_name', 'User'),
        valid_minutes=OTP_EXPIRY_MINUTES,
        ip_address=client_ip,
        device_info=device_str,
        base_url=base_url
    )
    if not mail_ok:
        session.pop('forgot_pending', None)
        session.pop('forgot_otp_sent_at', None)
        session.modified = True
        logger.error(f"Failed to dispatch password reset OTP email to {email}: {mail_err}")
        return False, f"Failed to deliver verification code email: {mail_err}", 500

    logger.info(f"Generated session-based password reset OTP for {email} (valid 3 mins)")
    return True, "Verification code sent to your email address.", 200


def verify_and_reset_password(
    email: str,
    otp_code: str,
    new_password: str,
    confirm_password: str,
    req=None,
    base_url: str = 'http://127.0.0.1:5000'
) -> Tuple[bool, str, int]:
    """
    Verifies the password reset OTP from session (3 min validity), validates password criteria,
    updates user password in MySQL database, and sends executive confirmation security email with
    browser, timestamp, and admin contact notice.
    """
    email = (email or '').strip().lower()
    otp_code = (otp_code or '').strip()
    new_password = str(new_password or '')
    confirm_password = str(confirm_password or '')

    if not email or not otp_code or not new_password:
        return False, "Email, 6-digit verification code, and new password are required.", 400

    if new_password != confirm_password:
        return False, "Passwords do not match.", 400

    if len(new_password) < 6:
        return False, "New password must be at least 6 characters long.", 400

    try:
        settings = current_app.config.get('SYSTEM_SETTINGS', {}) if current_app else {}
    except Exception:
        settings = {}

    if settings.get('enforce_strong_passwords', True):
        if len(new_password) < 8 or not any(c.isupper() for c in new_password) or not any(c.isdigit() for c in new_password):
            return False, "Password must be at least 8 characters long and contain at least one uppercase letter and one number.", 400

    pending = session.get('forgot_pending')
    if not pending or pending.get('email') != email:
        return False, "No active password reset session found. Please request a new code.", 404

    now_ts = time.time()

    # 1. Check expiration (3 minutes)
    if now_ts > pending.get('expires_at', 0):
        session.pop('forgot_pending', None)
        session.modified = True
        return False, "Verification code has expired (3 minutes validity). Please request a new code.", 400

    # 2. Check maximum attempts
    attempts = pending.get('attempts', 0)
    if attempts >= MAX_VERIFICATION_ATTEMPTS:
        session.pop('forgot_pending', None)
        session.modified = True
        return False, "Maximum verification attempts exceeded. Please request a new code.", 429

    # 3. Check code match
    if str(pending.get('otp_code')) != str(otp_code):
        attempts += 1
        pending['attempts'] = attempts
        session['forgot_pending'] = pending
        session.modified = True
        remaining = MAX_VERIFICATION_ATTEMPTS - attempts
        if remaining > 0:
            return False, f"Incorrect verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.", 400
        else:
            session.pop('forgot_pending', None)
            session.modified = True
            return False, "Maximum verification attempts reached. Please request a new code.", 429

    # 4. Hash new password and update user record in database
    conn = get_db_connection()
    if not conn:
        return False, "Database connection error. Please try again later.", 500

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, first_name FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            if not user:
                return False, "No account found with this email address.", 404

            hashed_pwd = bcrypt.generate_password_hash(new_password).decode('utf-8')
            cursor.execute(
                "UPDATE users SET password = %s WHERE email = %s",
                (hashed_pwd, email)
            )
            conn.commit()

        first_name = user.get('first_name', 'User')

        # 5. Clear session state
        session.pop('forgot_pending', None)
        session.pop('forgot_otp_sent_at', None)
        session.modified = True

        # 6. Send executive confirmation security email detailing browser, timestamp & admin contact
        device_str, client_ip, location_str = email_service.parse_client_device(req)
        try:
            email_service.send_password_reset_success_email(
                user_email=email,
                first_name=first_name,
                ip_address=client_ip,
                device_info=device_str,
                location=location_str,
                base_url=base_url
            )
        except Exception as alert_err:
            logger.warning(f"Failed to dispatch password reset success email: {alert_err}")

        logger.info(f"Successfully reset password for {email}")
        return True, "Password reset successfully! Redirecting to login...", 200

    except Exception as e:
        logger.error(f"Error resetting password for {email}: {e}")
        return False, f"Password reset failed: {str(e)}", 500
    finally:
        conn.close()


def resend_forgot_password_otp(
    email: str,
    req=None,
    base_url: str = 'http://127.0.0.1:5000'
) -> Tuple[bool, str, int]:
    """Resends a fresh 3-minute OTP for an existing forgot password session with cooldown enforcement."""
    email = (email or '').strip().lower()
    if not email:
        return False, "Email address is required.", 400

    pending = session.get('forgot_pending')
    if not pending or pending.get('email') != email:
        return False, "No active password reset request found. Please enter your email to request a code.", 404

    now_ts = time.time()
    last_sent = session.get('forgot_otp_sent_at', 0)
    if (now_ts - last_sent) < RESEND_COOLDOWN_SECONDS:
        wait_sec = int(RESEND_COOLDOWN_SECONDS - (now_ts - last_sent))
        return False, f"Please wait {wait_sec} seconds before requesting a new code.", 429

    new_otp = generate_otp()
    pending['otp_code'] = new_otp
    pending['expires_at'] = now_ts + OTP_EXPIRY_SECONDS
    pending['attempts'] = 0
    session['forgot_pending'] = pending
    session['forgot_otp_sent_at'] = now_ts
    session.modified = True

    device_str, client_ip, _ = email_service.parse_client_device(req)
    logger.info(f"🔑 [DATANOVA OTP] Resent password reset OTP for {email}: {new_otp}")
    mail_ok, mail_err = email_service.send_forgot_password_otp_email(
        user_email=email,
        otp_code=new_otp,
        first_name=pending.get('first_name', 'User'),
        valid_minutes=OTP_EXPIRY_MINUTES,
        ip_address=client_ip,
        device_info=device_str,
        base_url=base_url
    )
    if not mail_ok:
        logger.error(f"Failed to resend password reset OTP email to {email}: {mail_err}")
        return False, f"Failed to deliver verification code email: {mail_err}", 500

    return True, "A new verification code has been sent to your email address.", 200
