from flask import Blueprint, render_template, session, flash, redirect, url_for, jsonify, current_app
from .auth import login_required
from database.db_connector import get_db_connection
from .services import manager_service, viewer_service, admin_service, analyst_service

bp = Blueprint('dashboards', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/.well-known/appspecific/com.chrome.devtools.json')
def chrome_devtools_config():
    return jsonify({})


@bp.route('/dashboard/admin')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Access denied. You do not have permission to view this page.', 'danger')
        return redirect(url_for('dashboards.index'))

    user = None
    conn = get_db_connection()

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['id'],))
                user = cursor.fetchone()
        except Exception as e:
            current_app.logger.error(f"Error fetching user for admin dashboard: {e}")

    kpi_data = admin_service.get_admin_dashboard_analytics(conn)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template('user/admin_dashboard.html', user=user, kpi=kpi_data)


@bp.route('/dashboard/manager')
@login_required
def manager_dashboard():
    if session.get('role') not in ['admin', 'manager']:
        flash('Access denied. You do not have permission to view this page.', 'danger')
        return redirect(url_for('dashboards.index'))

    user = None
    df = None
    conn = get_db_connection()

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['id'],))
                user = cursor.fetchone()

                # Determine active dataset ID
                active_ds_id = session.get('active_dataset_id')
                if not active_ds_id:
                    cursor.execute("SELECT id FROM datasets ORDER BY uploaded_at DESC LIMIT 1")
                    ds_row = cursor.fetchone()
                    if ds_row:
                        active_ds_id = ds_row['id']
                        session['active_dataset_id'] = active_ds_id

                if active_ds_id:
                    try:
                        from .api import load_dataframe
                        df = load_dataframe(active_ds_id, session['id'])
                    except Exception as ex:
                        current_app.logger.warning(f"Could not load active dataframe for manager dashboard: {ex}")

        except Exception as e:
            current_app.logger.error(f"Error loading user/dataset for manager dashboard: {e}")
            flash('An error occurred while loading dashboard user data.', 'danger')

    # Compute complete dynamic manager analytics using manager_service
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
    if session.get('role') not in ['admin', 'manager', 'analyst']:
        flash('Access denied. You do not have permission to view this page.', 'danger')
        return redirect(url_for('dashboards.index'))

    user = None
    df = None
    conn = get_db_connection()

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['id'],))
                user = cursor.fetchone()

                active_ds_id = session.get('active_dataset_id')
                if not active_ds_id:
                    cursor.execute(
                        "SELECT id FROM datasets WHERE user_id = %s ORDER BY uploaded_at DESC LIMIT 1",
                        (session['id'],)
                    )
                    latest_dataset = cursor.fetchone()
                    if latest_dataset:
                        active_ds_id = latest_dataset['id']
                        session['active_dataset_id'] = active_ds_id

                if active_ds_id:
                    try:
                        from .api import load_dataframe
                        df = load_dataframe(active_ds_id, session['id'])
                    except Exception as ex:
                        current_app.logger.warning(f"Could not load active dataframe for analyst dashboard: {ex}")
        except Exception as e:
            current_app.logger.error(f"Error loading user/dataset for analyst dashboard: {e}")
            flash('An error occurred while loading dashboard data.', 'danger')

    kpi_data = analyst_service.get_analyst_dashboard_analytics(df, conn, session.get('id'))

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template(
        'user/analyst_dashboard.html',
        user=user,
        kpi=kpi_data,
        active_dataset_id=session.get('active_dataset_id')
    )


@bp.route('/dashboard/viewer')
@login_required
def viewer_dashboard():
    role = session.get('role', 'viewer')
    if role not in ['admin', 'manager', 'analyst', 'viewer']:
        flash('Access denied. You do not have permission to view this page.', 'danger')
        return redirect(url_for('dashboards.index'))

    user = None
    df = None
    conn = get_db_connection()

    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM users WHERE id = %s", (session['id'],))
                user = cursor.fetchone()

                active_ds_id = session.get('active_dataset_id')
                if not active_ds_id:
                    cursor.execute("SELECT id FROM datasets ORDER BY uploaded_at DESC LIMIT 1")
                    ds_row = cursor.fetchone()
                    if ds_row:
                        active_ds_id = ds_row['id']
                        session['active_dataset_id'] = active_ds_id

                if active_ds_id:
                    try:
                        from .api import load_dataframe
                        df = load_dataframe(active_ds_id, session['id'])
                    except Exception as ex:
                        current_app.logger.warning(f"Could not load active dataframe for viewer dashboard: {ex}")

        except Exception as e:
            current_app.logger.error(f"Error loading viewer dashboard user/dataset: {e}")
            flash('An error occurred while loading dashboard user data.', 'danger')

    # Get complete dynamic analytics for viewer
    analytics = viewer_service.get_viewer_dashboard_analytics(df, conn, session.get('id'), role)

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    return render_template(
        'user/viewer_dashboard.html',
        user=user,
        kpi=analytics['kpi'],
        shared_dashboards=analytics['shared_dashboards'],
        reports=analytics['reports'],
        notifications=analytics['notifications'],
        analytics=analytics,
        insights=analytics['insights']
    )