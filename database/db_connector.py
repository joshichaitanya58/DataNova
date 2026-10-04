import os
import time
import queue
import logging
import threading
from typing import Optional, Any
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class PooledConnectionWrapper:
    """
    Wraps a raw PyMySQL connection so that when `close()` is called by application code,
    the connection is returned to the pool instead of terminating the socket.
    """
    def __init__(self, raw_conn: pymysql.connections.Connection, pool: "DataNovaConnectionPool"):
        self._raw_conn = raw_conn
        self._pool = pool
        self._is_closed = False

    def _check_closed(self):
        if self._is_closed:
            raise DatabaseConnectionError("Cannot perform operation on closed database connection wrapper.")

    def __getattr__(self, name: str) -> Any:
        self._check_closed()
        return getattr(self._raw_conn, name)

    def close(self):
        if not self._is_closed:
            self._is_closed = True
            self._pool.release_connection(self._raw_conn)

    def cursor(self, cursor_type=DictCursor):
        self._check_closed()
        return self._raw_conn.cursor(cursor_type)

    def commit(self):
        self._check_closed()
        return self._raw_conn.commit()

    def rollback(self):
        self._check_closed()
        return self._raw_conn.rollback()

    def ping(self, reconnect=True):
        self._check_closed()
        return self._raw_conn.ping(reconnect=reconnect)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self.rollback()
            except Exception:
                pass
        self.close()


class DataNovaConnectionPool:
    """
    Thread-safe, high-concurrency connection pool capable of sustaining 1,000+ simultaneous users.
    Features:
    - Pre-warmed connection cache
    - Connection health verification (ping & auto-reconnect)
    - Thread-safe acquire and release with timeout
    - Auto-recycling of stale connections
    """
    def __init__(self, max_connections: int = 50, timeout: float = 10.0):
        self._max_connections = max_connections
        self._timeout = timeout
        self._pool: queue.Queue = queue.Queue(maxsize=max_connections)
        self._created_count = 0
        self._lock = threading.Lock()
        self._db_config = {}
        self._initialized = False

    def _load_config(self):
        db_host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or os.getenv("MYSQL_HOST")
        db_user = os.getenv("DB_USER") or os.getenv("MYSQLUSER") or os.getenv("MYSQL_USER")
        db_password = os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_PASSWORD")
        db_name = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or os.getenv("MYSQL_DATABASE")
        db_port_str = os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or os.getenv("MYSQL_PORT") or "3306"

        if not all([db_host, db_user, db_password, db_name]):
            raise DatabaseConnectionError("Missing critical DB configuration variables in environment (DB_HOST/MYSQLHOST, DB_USER/MYSQLUSER, DB_PASSWORD/MYSQLPASSWORD, DB_NAME/MYSQLDATABASE).")

        port = int(db_port_str) if db_port_str.isdigit() else 3306
        self._db_config = {
            "host": db_host,
            "port": port,
            "user": db_user,
            "password": db_password,
            "database": db_name,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "connect_timeout": 10,
            "read_timeout": 30,
            "write_timeout": 30,
            "autocommit": False,
        }
        self._initialized = True

    def _create_raw_connection(self) -> pymysql.connections.Connection:
        if not self._initialized:
            self._load_config()
        conn = pymysql.connect(**self._db_config)
        return conn

    def get_connection(self, raise_on_error: bool = False) -> Optional[PooledConnectionWrapper]:
        """Acquires a pooled connection with health check and auto-healing."""
        if not self._initialized:
            try:
                self._load_config()
            except Exception as e:
                logger.error(f"Failed to load DB config: {e}")
                if raise_on_error:
                    raise DatabaseConnectionError(str(e)) from e
                return None

        # 1. Try to get an existing connection from the pool
        try:
            raw_conn = self._pool.get_nowait()
            try:
                raw_conn.ping(reconnect=True)
                return PooledConnectionWrapper(raw_conn, self)
            except Exception:
                # Connection was dead, recreate
                try:
                    raw_conn.close()
                except Exception:
                    pass
                with self._lock:
                    self._created_count = max(0, self._created_count - 1)
        except queue.Empty:
            pass

        # 2. If pool is not full, increment count under lock and create connection outside lock
        can_create = False
        with self._lock:
            if self._created_count < self._max_connections:
                self._created_count += 1
                can_create = True

        if can_create:
            try:
                raw_conn = self._create_raw_connection()
                return PooledConnectionWrapper(raw_conn, self)
            except Exception as e:
                with self._lock:
                    self._created_count = max(0, self._created_count - 1)
                logger.error(f"Error creating new database connection: {e}")
                if raise_on_error:
                    raise DatabaseConnectionError(str(e)) from e
                return None

        # 3. Wait for an available connection with timeout
        try:
            raw_conn = self._pool.get(timeout=self._timeout)
            try:
                raw_conn.ping(reconnect=True)
            except Exception:
                try:
                    raw_conn.close()
                except Exception:
                    pass
                raw_conn = self._create_raw_connection()
            return PooledConnectionWrapper(raw_conn, self)
        except queue.Empty:
            msg = f"Database connection pool exhausted ({self._max_connections} active connections). Request timed out."
            logger.error(msg)
            if raise_on_error:
                raise DatabaseConnectionError(msg)
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting connection from pool: {e}")
            if raise_on_error:
                raise DatabaseConnectionError(str(e)) from e
            return None

    def release_connection(self, raw_conn: pymysql.connections.Connection):
        """Returns a healthy connection back into the pool."""
        if raw_conn is None:
            return
        try:
            try:
                raw_conn.rollback()
            except Exception:
                pass
            self._pool.put_nowait(raw_conn)
        except queue.Full:
            try:
                raw_conn.close()
            except Exception:
                pass
            with self._lock:
                self._created_count = max(0, self._created_count - 1)


# Global Singleton Database Connection Pool
_global_db_pool = DataNovaConnectionPool(max_connections=50, timeout=10.0)


def get_db_connection(raise_on_error: bool = False) -> Optional[PooledConnectionWrapper]:
    """
    Returns a pooled, thread-safe MySQL connection.
    Supports both traditional `.close()` and context manager usage (`with get_db_connection() as conn:`).
    """
    return _global_db_pool.get_connection(raise_on_error=raise_on_error)


def init_db(connection: Optional[Any] = None) -> bool:
    """
    Initializes the database schema and automatically configures high-concurrency indexes.
    Safe to execute on every application startup.
    """
    close_after = False
    if connection is None:
        connection = get_db_connection(raise_on_error=False)
        if connection is None:
            logger.warning("Auto DB Initialization skipped: database connection not available.")
            return False
        close_after = True

    tables_ddl = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'developer',
            organization VARCHAR(100) NOT NULL DEFAULT 'General',
            phone VARCHAR(30) DEFAULT NULL,
            bio TEXT DEFAULT NULL,
            api_key VARCHAR(100) DEFAULT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_users_org_role (organization, role),
            INDEX idx_users_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS datasets (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            file_size BIGINT,
            file_type VARCHAR(10),
            row_count BIGINT UNSIGNED,
            column_count INT UNSIGNED,
            missing_values_count BIGINT UNSIGNED DEFAULT 0,
            duplicate_rows_count BIGINT UNSIGNED DEFAULT 0,
            status VARCHAR(20) DEFAULT 'uploaded',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            eda_charts_json JSON,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_datasets_user_status (user_id, status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            dataset_id INT NOT NULL,
            report_name VARCHAR(255) NOT NULL,
            report_type VARCHAR(50) DEFAULT 'HTML',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
            INDEX idx_reports_user_dataset (user_id, dataset_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS api_usage_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            endpoint VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL,
            is_ai_call BOOLEAN DEFAULT FALSE,
            called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_api_usage_user_called (user_id, called_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS shared_dashboards (
            id INT AUTO_INCREMENT PRIMARY KEY,
            owner_id INT NOT NULL,
            shared_with_role VARCHAR(20) DEFAULT NULL,
            shared_with_user_id INT DEFAULT NULL,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            dataset_id INT,
            status VARCHAR(20) DEFAULT 'Shared',
            remark TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (shared_with_user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
            INDEX idx_shared_owner (owner_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS manager_team_members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            manager_id INT NOT NULL,
            user_id INT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE KEY manager_user_unique (manager_id, user_id),
            INDEX idx_team_manager (manager_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS manager_tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            manager_id INT NOT NULL,
            assigned_to_id INT NOT NULL,
            task_title VARCHAR(255) NOT NULL,
            description TEXT,
            priority VARCHAR(20) DEFAULT 'Medium',
            status VARCHAR(20) DEFAULT 'Pending',
            due_date DATE,
            remark TEXT,
            dataset_id INT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_to_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
            INDEX idx_tasks_mgr_assigned (manager_id, assigned_to_id, status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(20) DEFAULT 'info',
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_notifs_user (user_id, is_read)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS system_settings (
            setting_key VARCHAR(100) PRIMARY KEY,
            setting_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS developer_api_keys (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            key_name VARCHAR(100) NOT NULL DEFAULT 'Default API Key',
            key_prefix VARCHAR(20) NOT NULL DEFAULT 'dn_live_',
            key_hash VARCHAR(128) NOT NULL,
            key_last_chars VARCHAR(10) NOT NULL,
            environment VARCHAR(10) NOT NULL DEFAULT 'live',
            scopes TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            last_used_at TIMESTAMP NULL DEFAULT NULL,
            expires_at TIMESTAMP NULL DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_keys_user_status (user_id, status),
            INDEX idx_keys_hash (key_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS api_dataset_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_format VARCHAR(20) NOT NULL DEFAULT 'csv',
            file_size BIGINT DEFAULT 0,
            row_count BIGINT UNSIGNED DEFAULT 0,
            column_count INT UNSIGNED DEFAULT 0,
            retention_status VARCHAR(50) DEFAULT 'PROCESSED & PURGED',
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_api_datasets_user (user_id, ingested_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS contact_admin_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            user_name VARCHAR(150) NOT NULL,
            user_email VARCHAR(150) NOT NULL,
            user_role VARCHAR(50) DEFAULT 'user',
            subject VARCHAR(255) NOT NULL,
            category VARCHAR(50) DEFAULT 'General Inquiry',
            message TEXT NOT NULL,
            attachment_url VARCHAR(500) DEFAULT NULL,
            status VARCHAR(20) DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_contact_user (user_id, status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]


    try:
        with connection.cursor() as cursor:
            for ddl in tables_ddl:
                cursor.execute(ddl)

            # Auto-migrations for datasets table columns
            cursor.execute("SHOW COLUMNS FROM datasets LIKE 'is_api_dataset'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE datasets ADD COLUMN is_api_dataset TINYINT DEFAULT 0")

            # Auto-migration for contact_admin_messages attachment_url
            cursor.execute("SHOW COLUMNS FROM contact_admin_messages LIKE 'attachment_url'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE contact_admin_messages ADD COLUMN attachment_url VARCHAR(500) DEFAULT NULL")

            # Auto-migrations for existing users table columns
            cursor.execute("SHOW COLUMNS FROM users LIKE 'organization'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN organization VARCHAR(100) NOT NULL DEFAULT 'General'")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'phone'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(30) DEFAULT NULL")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'bio'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT DEFAULT NULL")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'api_key'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN api_key VARCHAR(100) DEFAULT NULL")

            # Auto-migrations for shared_dashboards table columns
            cursor.execute("SHOW COLUMNS FROM shared_dashboards LIKE 'status'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE shared_dashboards ADD COLUMN status VARCHAR(20) DEFAULT 'Shared'")

            cursor.execute("SHOW COLUMNS FROM shared_dashboards LIKE 'remark'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE shared_dashboards ADD COLUMN remark TEXT DEFAULT NULL")


            cursor.execute("SHOW COLUMNS FROM shared_dashboards LIKE 'updated_at'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE shared_dashboards ADD COLUMN updated_at TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP")

            # Auto-migrations for manager_tasks table columns
            cursor.execute("SHOW COLUMNS FROM manager_tasks LIKE 'remark'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE manager_tasks ADD COLUMN remark TEXT DEFAULT NULL")

            cursor.execute("SHOW COLUMNS FROM manager_tasks LIKE 'dataset_id'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE manager_tasks ADD COLUMN dataset_id INT DEFAULT NULL")

            # Auto-migrations for api_usage_logs telemetry columns
            api_log_columns = [
                ("request_id", "VARCHAR(64) DEFAULT NULL"),
                ("api_key_id", "INT DEFAULT NULL"),
                ("environment", "VARCHAR(10) DEFAULT 'live'"),
                ("method", "VARCHAR(10) DEFAULT 'GET'"),
                ("status_code", "INT DEFAULT 200"),
                ("response_time_ms", "INT DEFAULT 0"),
                ("dataset_id", "INT DEFAULT NULL"),
                ("analysis_id", "VARCHAR(64) DEFAULT NULL"),
                ("error_code", "VARCHAR(50) DEFAULT NULL"),
                ("error_message", "TEXT DEFAULT NULL"),
                ("request_params", "TEXT DEFAULT NULL"),
                ("response_summary", "TEXT DEFAULT NULL")
            ]
            for col_name, col_def in api_log_columns:
                cursor.execute(f"SHOW COLUMNS FROM api_usage_logs LIKE '{col_name}'")
                if not cursor.fetchone():
                    cursor.execute(f"ALTER TABLE api_usage_logs ADD COLUMN {col_name} {col_def}")

            # High-concurrency performance index additions
            index_queries = [
                "CREATE INDEX idx_users_org_role ON users (organization, role)",
                "CREATE INDEX idx_users_status ON users (status)",
                "CREATE INDEX idx_datasets_user_status ON datasets (user_id, status)",
                "CREATE INDEX idx_tasks_mgr_assigned ON manager_tasks (manager_id, assigned_to_id, status)",
                "CREATE INDEX idx_reports_user_dataset ON reports (user_id, dataset_id)",
                "CREATE INDEX idx_api_usage_user_called ON api_usage_logs (user_id, called_at)",
                "CREATE INDEX idx_api_usage_req_id ON api_usage_logs (request_id)"
            ]
            for idx_q in index_queries:
                try:
                    cursor.execute(idx_q)
                except Exception as idx_err:
                    err_str = str(idx_err)
                    if "1061" in err_str or "Duplicate key name" in err_str:
                        pass  # Index already exists
                    else:
                        logger.warning(f"Note on index creation '{idx_q}': {idx_err}")

        connection.commit()
        logger.info("Database tables and high-concurrency indexes verified/created successfully.")
        
        # Purge logs older than 30 days (720 hours) & start retention scheduler
        try:
            purge_expired_logs(hours=720)
            start_log_cleanup_scheduler(interval_seconds=3600, hours=720)
        except Exception as purge_err:
            logger.warning(f"Initial log purge / scheduler start failed: {purge_err}")

        return True
    except Exception as e:
        logger.error(f"Error during automatic database tables creation: {e}", exc_info=True)
        try:
            connection.rollback()
        except Exception:
            pass
        return False
    finally:
        if close_after:
            try:
                connection.close()
            except Exception:
                pass


_cleanup_scheduler_started = False

def purge_expired_logs(hours=720):
    """
    Automatically purges log entries older than specified hours (default 720 hours / 30 days).
    Targets api_usage_logs and api_dataset_logs database tables.
    """
    connection = get_db_connection()
    if not connection:
        return 0

    total_purged = 0
    try:
        with connection.cursor() as cursor:
            # 1. Purge API usage logs older than specified retention hours (default 30 days / 720h)
            cursor.execute("DELETE FROM api_usage_logs WHERE called_at < NOW() - INTERVAL %s HOUR", (hours,))
            purged_usage = cursor.rowcount or 0

            # 2. Purge API dataset telemetry logs older than specified retention hours (default 30 days / 720h)
            cursor.execute("DELETE FROM api_dataset_logs WHERE ingested_at < NOW() - INTERVAL %s HOUR", (hours,))
            purged_datasets = cursor.rowcount or 0

            connection.commit()
            total_purged = purged_usage + purged_datasets
            if total_purged > 0:
                logger.info(f"Auto-purged {total_purged} expired log records older than {hours} hours / 30 days (api_usage_logs: {purged_usage}, api_dataset_logs: {purged_datasets}).")
    except Exception as e:
        logger.warning(f"Error purging expired logs (> {hours}h): {e}")
        try:
            connection.rollback()
        except Exception:
            pass
    finally:
        try:
            connection.close()
        except Exception:
            pass

    return total_purged


def start_log_cleanup_scheduler(interval_seconds=3600, hours=720):
    """
    Starts a background daemon thread that periodically runs log retention purging every hour.
    """
    if os.getenv('VERCEL') or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        return
    global _cleanup_scheduler_started
    if _cleanup_scheduler_started:
        return
    _cleanup_scheduler_started = True

    def _worker():
        while True:
            try:
                purge_expired_logs(hours=hours)
            except Exception as err:
                logger.warning(f"Background log cleanup worker exception: {err}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_worker, daemon=True, name="LogCleanupScheduler")
    thread.start()
    logger.info(f"Background 30-day ({hours}-hour) log retention scheduler active (Interval: {interval_seconds}s).")


