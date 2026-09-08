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


def get_db_connection(raise_on_error: bool = False) -> Optional[pymysql.connections.Connection]:
    """
    Creates and returns a safe MySQL database connection.

    Args:
        raise_on_error (bool): If True, raises DatabaseConnectionError on failure.
                               If False (default), logs error and returns None.

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
        msg = f"Missing database configuration: {', '.join(missing)}"
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
        return connection

    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        if raise_on_error:
            raise DatabaseConnectionError(f"Unable to connect to database: {str(e)}") from e
        return None