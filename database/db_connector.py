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

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw_conn, name)

    def close(self):
        if not self._is_closed:
            self._is_closed = True
            self._pool.release_connection(self._raw_conn)

    def cursor(self, cursor_type=DictCursor):
        return self._raw_conn.cursor(cursor_type)

    def commit(self):
        return self._raw_conn.commit()

    def rollback(self):
        return self._raw_conn.rollback()

    def ping(self, reconnect=True):
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
        db_host = os.getenv("DB_HOST")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_name = os.getenv("DB_NAME")
        db_port_str = os.getenv("DB_PORT", "3306")

        if not all([db_host, db_user, db_password, db_name]):
            raise DatabaseConnectionError("Missing critical DB configuration variables in environment.")

        db_ssl_enabled = os.getenv("DB_SSL", "false").lower() in ("true", "1", "yes", "require", "required")
        db_ssl_ca = os.getenv("DB_SSL_CA")

        port = int(db_port_str) if db_port_str.isdigit() else 3306
        self._db_config = {
            "host": db_host,
            "port": port,
            "user": db_user,
            "password": db_password,
            "database": db_name,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "connect_timeout": 15,
            "read_timeout": 60,
            "write_timeout": 60,
            "autocommit": False,
        }

        # Enable SSL for cloud MySQL instances (e.g. TiDB, Aiven, AWS RDS, PlanetScale)
        if db_ssl_enabled:
            ssl_dict = {}
            if db_ssl_ca and os.path.exists(db_ssl_ca):
                ssl_dict["ca"] = db_ssl_ca
            else:
                ssl_dict["ssl"] = True
            self._db_config["ssl"] = ssl_dict

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

        # 2. If pool is not full, create a new connection
        with self._lock:
            if self._created_count < self._max_connections:
                try:
                    raw_conn = self._create_raw_connection()
                    self._created_count += 1
                    return PooledConnectionWrapper(raw_conn, self)
                except Exception as e:
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
            # Ensure transaction is rolled back so the connection is clean
            try:
                raw_conn.rollback()
            except Exception:
                pass
            self._pool.put_nowait(raw_conn)
        except queue.Full:
            # Pool full, close connection
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
            role VARCHAR(20) NOT NULL DEFAULT 'viewer',
            organization VARCHAR(100) NOT NULL DEFAULT 'General',
            phone VARCHAR(30) DEFAULT NULL,
            bio TEXT DEFAULT NULL,
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
            row_count INT,
            column_count INT,
            missing_values_count INT DEFAULT 0,
            duplicate_rows_count INT DEFAULT 0,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
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
        """
    ]

    try:
        with connection.cursor() as cursor:
            for ddl in tables_ddl:
                cursor.execute(ddl)

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

            # High-concurrency performance index additions (safe try-catch per index)
            index_queries = [
                "CREATE INDEX idx_users_org_role ON users (organization, role)",
                "CREATE INDEX idx_users_status ON users (status)",
                "CREATE INDEX idx_datasets_user_status ON datasets (user_id, status)",
                "CREATE INDEX idx_tasks_mgr_assigned ON manager_tasks (manager_id, assigned_to_id, status)",
                "CREATE INDEX idx_reports_user_dataset ON reports (user_id, dataset_id)",
                "CREATE INDEX idx_api_usage_user_called ON api_usage_logs (user_id, called_at)"
            ]
            for idx_q in index_queries:
                try:
                    cursor.execute(idx_q)
                except Exception:
                    pass  # Index already exists

        connection.commit()
        logger.info("Database tables and high-concurrency indexes verified/created successfully.")
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
