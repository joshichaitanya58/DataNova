import os
import logging
from typing import Optional

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


def init_db_schema(connection: pymysql.connections.Connection):
    """
    Ensures all required tables exist in the database.
    """
    tables_sql = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            first_name VARCHAR(50) NOT NULL,
            last_name VARCHAR(50) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) NOT NULL DEFAULT 'viewer',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
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
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS api_usage_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            endpoint VARCHAR(255) NOT NULL,
            status VARCHAR(20) NOT NULL,
            is_ai_call BOOLEAN DEFAULT FALSE,
            called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
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
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE SET NULL
        );
        """
    ]
    try:
        with connection.cursor() as cursor:
            for sql in tables_sql:
                cursor.execute(sql)
        connection.commit()
    except Exception as e:
        logger.warning(f"Auto-schema initialization notice: {e}")


def get_db_connection(raise_on_error: bool = False, auto_init: bool = False) -> Optional[pymysql.connections.Connection]:
    """
    Creates and returns a safe MySQL database connection.

    Args:
        raise_on_error (bool): If True, raises DatabaseConnectionError on failure.
                               If False (default), logs error and returns None.
        auto_init (bool): If True, automatically creates any missing database tables.

    Returns:
        Optional[pymysql.connections.Connection]: Active connection or None.
    """
    db_host = os.getenv("DB_HOST")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_port_str = os.getenv("DB_PORT", "3306")

    missing = []
    if not db_host:
        missing.append("DB_HOST")
    if not db_user:
        missing.append("DB_USER")
    if not db_password:
        missing.append("DB_PASSWORD")
    if not db_name:
        missing.append("DB_NAME")

    if missing:
        msg = f"Missing database configuration in environment variables: {', '.join(missing)}"
        logger.warning(msg)
        if raise_on_error:
            raise DatabaseConnectionError(msg)
        return None

    try:
        port = int(db_port_str)
        if not (1 <= port <= 65535):
            raise ValueError
    except ValueError:
        msg = f"Invalid DB_PORT configuration: '{db_port_str}' must be an integer between 1 and 65535."
        logger.warning(msg)
        if raise_on_error:
            raise DatabaseConnectionError(msg)
        return None

    # SSL configuration for cloud-hosted databases (e.g. TiDB, Aiven, PlanetScale, Railway)
    db_ssl = os.getenv("DB_SSL", "false").lower() in ("true", "1", "t", "yes")
    ssl_config = None
    if db_ssl:
        ssl_config = {"ssl": {}}
        db_ssl_ca = os.getenv("DB_SSL_CA")
        if db_ssl_ca:
            ssl_config = {"ca": db_ssl_ca}

    try:
        connect_kwargs = {
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
        if ssl_config:
            connect_kwargs["ssl"] = ssl_config

        connection = pymysql.connect(**connect_kwargs)
        if auto_init:
            init_db_schema(connection)
        return connection

    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        if raise_on_error:
            raise DatabaseConnectionError(f"Unable to connect to database: {str(e)}") from e
        return None