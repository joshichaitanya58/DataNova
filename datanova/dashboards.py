from flask import Blueprint, render_template, session, flash, redirect, url_for, jsonify, current_app, request
from .auth import login_required
from database.db_connector import get_db_connection
from .services import manager_service, developer_service, admin_service, analyst_service

bp = Blueprint('dashboards', __name__)


def get_user_dashboard_redirect(role):
    """Returns the canonical dashboard URL for a given user role."""
    role_clean = (role or 'developer').lower().strip()
    if role_clean == 'admin':
        return url_for('dashboards.admin_dashboard')
    elif role_clean == 'manager':
        return url_for('dashboards.manager_dashboard')
    elif role_clean == 'analyst':
        return url_for('dashboards.analyst_dashboard')
    else:
        return url_for('dashboards.developer_dashboard')


def verify_user_access(allowed_roles, target_dashboard_name="this"):
    """
    Verifies user authentication, active database status, and role permissions.
    Fetches actual user account from DB to ensure session role & status are in sync.
    Returns (user_dict, conn, redirect_response). If redirect_response is not None,
    the caller must return it immediately.
    """
    user_id = session.get('id')
    if not user_id:
        flash('Please log in to access this page.', 'warning')
        return None, None, redirect(url_for('auth.login'))

    conn = get_db_connection()
    user = None
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
        except Exception as e:
            current_app.logger.error(f"Error fetching user for access verification: {e}")

    if not user:
        session.clear()
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        flash('User account not found. Please log in again.', 'danger')
        return None, None, redirect(url_for('auth.login'))

    status = (user.get('status') or 'active').lower().strip()
    if status == 'inactive':
        session.clear()
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        flash('Your account has been deactivated. Please contact the system administrator.', 'danger')
        return None, None, redirect(url_for('auth.login'))

    db_role = (user.get('role') or 'developer').lower().strip()
    session['role'] = db_role  # Keep session synchronized with actual DB role

    # Maintenance mode check - block non-admins
    settings = current_app.config.get('SYSTEM_SETTINGS', {})
    if settings.get('maintenance_mode') and db_role != 'admin':
        session.clear()
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        flash('System is currently under maintenance. Access is restricted to Admins only.', 'warning')
        return None, None, redirect(url_for('auth.login'))

    if db_role not in allowed_roles:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        flash(
            f"Access denied! Your role ('{db_role.capitalize()}') does not have permission to access the {target_dashboard_name} dashboard.",
            'danger'
        )
        return None, None, redirect(get_user_dashboard_redirect(db_role))

    return user, conn, None


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools_config():
    return jsonify({})


@bp.route('/dashboard/admin')
@login_required
def admin_dashboard():
    user, conn, err_redirect = verify_user_access(['admin'], "Admin")
    if err_redirect:
        return err_redirect

    kpi_data = admin_service.get_admin_dashboard_analytics(conn)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template('user/admin_dashboard.html', user=user, kpi=kpi_data)


@bp.route('/dashboard/admin/reports')
@login_required
def admin_reports_dashboard():
    user, conn, err_redirect = verify_user_access(['admin', 'manager'], "Reports")
    if err_redirect:
        return err_redirect

    reports = admin_service.get_all_admin_reports(conn)
    kpi_data = admin_service.get_admin_dashboard_analytics(conn)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({'success': True, 'reports': reports, 'count': len(reports)})

    return render_template('user/admin_dashboard.html', user=user, kpi=kpi_data, reports=reports, reports_active=True)


@bp.route('/dashboard/manager')
@login_required
def manager_dashboard():
    user, conn, err_redirect = verify_user_access(['admin', 'manager'], "Manager")
    if err_redirect:
        return err_redirect

    df = None
    if conn:
        try:
            with conn.cursor() as cursor:
                active_ds_id = session.get('active_dataset_id')
                if not active_ds_id:
                    cursor.execute("""
                        SELECT d.id FROM datasets d
                        JOIN users u ON d.user_id = u.id
                        WHERE (
                            d.user_id = %s
                            OR d.user_id IN (SELECT user_id FROM manager_team_members WHERE manager_id = %s)
                            OR d.user_id IN (SELECT assigned_to_id FROM manager_tasks WHERE manager_id = %s)
                            OR (u.organization = %s AND u.role = 'analyst')
                        )
                        ORDER BY d.uploaded_at DESC LIMIT 1
                    """, (user['id'], user['id'], user['id'], user.get('organization', 'General')))
                    ds_row = cursor.fetchone()
                    if ds_row:
                        active_ds_id = ds_row['id']
                        session['active_dataset_id'] = active_ds_id

                if active_ds_id:
                    try:
                        cursor.execute("SELECT user_id FROM datasets WHERE id = %s", (active_ds_id,))
                        ds_meta = cursor.fetchone()
                        owner_id = ds_meta['user_id'] if ds_meta else session['id']
                        from .api import load_dataframe
                        df = load_dataframe(active_ds_id, owner_id)
                    except Exception as ex:
                        current_app.logger.warning(f"Could not load active dataframe for manager dashboard: {ex}")
        except Exception as e:
            current_app.logger.error(f"Error loading manager dataset: {e}")

    kpi_data = manager_service.get_manager_full_dashboard_analytics(df, conn, session.get('id'))

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template('user/manager_dashboard.html', user=user, kpi=kpi_data)


@bp.route('/dashboard/analyst')
@login_required
def analyst_dashboard():
    user, conn, err_redirect = verify_user_access(['admin', 'manager', 'analyst'], "Analyst")
    if err_redirect:
        return err_redirect

    user_id = session.get('id')
    active_ds_id = session.get('active_dataset_id')
    df = None

    if conn and user_id:
        try:
            with conn.cursor() as cursor:
                if active_ds_id:
                    cursor.execute("SELECT id FROM datasets WHERE id = %s AND user_id = %s", (active_ds_id, user_id))
                    row = cursor.fetchone()
                    if not row:
                        active_ds_id = None
                        session.pop('active_dataset_id', None)

            if active_ds_id:
                from .api import load_dataframe
                df = load_dataframe(active_ds_id, user_id)
        except Exception:
            df = None

    kpi_data = analyst_service.get_analyst_dashboard_analytics(df, conn, user_id)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template(
        'user/analyst_dashboard.html',
        user=user,
        kpi=kpi_data,
        active_dataset_id=active_ds_id
    )


@bp.route('/dashboard/developer')
@login_required
def developer_dashboard():
    user, conn, err_redirect = verify_user_access(['admin', 'manager', 'analyst', 'developer'], "Developer")
    if err_redirect:
        return err_redirect

    data = developer_service.get_developer_dashboard_analytics(session.get('id'), conn)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template(
        'user/developer_dashboard.html',
        user=user,
        api_key=data['api_key'],
        keys=data.get('keys', []),
        metrics=data['metrics'],
        endpoints=data['endpoints'],
        recent_logs=data['recent_logs'],
        failed_logs=data.get('failed_logs', []),
        daily_usage=data.get('daily_usage', [])
    )