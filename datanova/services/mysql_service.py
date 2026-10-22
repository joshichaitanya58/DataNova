import os
import re
import logging
import datetime
import decimal
from typing import Dict, Any, List, Optional, Tuple
import pymysql
from pymysql.cursors import DictCursor
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# List of SQL command keywords that should never be executed in read-only extraction
DESTRUCTIVE_SQL_KEYWORDS = {
    'insert', 'update', 'delete', 'drop', 'alter', 'truncate',
    'replace', 'create', 'rename', 'grant', 'revoke', 'call',
    'execute', 'exec', 'lock', 'unlock', 'shutdown'
}

SYSTEM_DATABASES = {'information_schema', 'performance_schema', 'mysql', 'sys'}
SYSTEM_TABLES = {'sys_config'}


def sanitize_identifier(name: str) -> str:
    """Sanitizes an SQL table or column identifier to avoid injection."""
    if not name:
        return ""
    # Only allow alphanumeric and underscores
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '', name.strip())
    return cleaned


def is_safe_read_query(query: str) -> Tuple[bool, str]:
    """
    Validates that a custom query is strictly read-only.
    Allows SELECT, WITH (CTE), SHOW, DESCRIBE, EXPLAIN.
    Rejects destructive statements or multi-statement attacks.
    """
    if not query or not query.strip():
        return False, "Query string cannot be empty."

    # Remove SQL single-line and multi-line comments
    cleaned = re.sub(r'--.*?(\r?\n|$)', ' ', query)
    cleaned = re.sub(r'/\*.*?\*/', ' ', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # Disallow multiple semicolons (prevent multi-statement chained attacks)
    statements = [s.strip() for s in cleaned.split(';') if s.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements separated by semicolons are not permitted for security."

    first_word = cleaned.split()[0].lower() if cleaned.split() else ""
    allowed_starters = {'select', 'with', 'show', 'describe', 'desc', 'explain'}
    if first_word not in allowed_starters:
        return False, f"Query must begin with a read-only keyword (e.g. SELECT, WITH, SHOW, DESCRIBE). '{first_word.upper()}' is not allowed."

    # Check for destructive keywords as whole words
    tokens = set(re.findall(r'\b[a-zA-Z_]+\b', cleaned.lower()))
    intersection = tokens.intersection(DESTRUCTIVE_SQL_KEYWORDS)
    if intersection:
        forbidden = ", ".join(sorted(intersection)).upper()
        return False, f"Destructive or mutating SQL operations ({forbidden}) are strictly prohibited."

    return True, ""


def get_mysql_connection(
    host: str = "localhost",
    port: int = 3306,
    user: str = "root",
    password: str = "",
    database: Optional[str] = None,
    timeout: int = 10
) -> pymysql.connections.Connection:
    """Creates a direct PyMySQL connection with health and timeout settings."""
    try:
        port_num = int(port) if str(port).strip().isdigit() else 3306
    except (ValueError, TypeError):
        port_num = 3306

    host_clean = host.strip() if host else "localhost"
    # On Windows, localhost can sometimes bind to IPv6 ::1; fallback is seamless
    conn = pymysql.connect(
        host=host_clean,
        port=port_num,
        user=user.strip() if user else "root",
        password=password if password is not None else "",
        database=database.strip() if database and database.strip() else None,
        charset='utf8mb4',
        cursorclass=DictCursor,
        connect_timeout=timeout,
        read_timeout=30,
        write_timeout=30,
        autocommit=False
    )
    return conn


def test_mysql_connection(
    host: str,
    port: Any,
    user: str,
    password: str,
    database: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tests connection to the specified MySQL instance and fetches tables.
    Strictly verifies user-provided credentials without using server environment secrets.
    """
    if not host or not str(host).strip():
        return {"success": False, "message": "Host is required (e.g. localhost or 127.0.0.1)."}
    if not user or not str(user).strip():
        return {"success": False, "message": "Username is required."}
    if not database or not str(database).strip():
        return {"success": False, "message": "Database name is required."}

    host = str(host).strip()
    user = str(user).strip()
    database = str(database).strip()

    conn = None
    try:
        conn = get_mysql_connection(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            timeout=6
        )
    except pymysql.err.OperationalError as op_err:
        code = op_err.args[0] if op_err.args else 0
        if code == 1045:
            return {
                "success": False,
                "message": f"Access denied for user '{user}' (Code 1045). Please verify password."
            }
        elif code == 2003:
            return {
                "success": False,
                "message": f"Cannot connect to MySQL server at {host}:{port} (Code 2003). Verify the server is running."
            }
        elif code == 1049:
            return {
                "success": False,
                "message": f"Database '{database}' does not exist on this MySQL server (Code 1049)."
            }
        return {
            "success": False,
            "message": f"MySQL Operational Error ({code}): {op_err.args[1] if len(op_err.args) > 1 else str(op_err)}"
        }
    except Exception as ex:
        return {"success": False, "message": f"Connection failed: {str(ex)}"}

    # Connected successfully - retrieve tables
    try:
        tables = []
        with conn.cursor() as cur:
            cur.execute(f"USE `{sanitize_identifier(database)}`;")
            cur.execute("SHOW TABLES;")
            for r in (cur.fetchall() or []):
                vals = list(r.values())
                if vals:
                    tbl = str(vals[0])
                    if tbl not in SYSTEM_TABLES:
                        tables.append(tbl)
            tables.sort()

        return {
            "success": True,
            "message": f"Connected successfully! {len(tables)} table(s) found in '{database}'.",
            "tables": tables,
            "database": database
        }
    except Exception as ex:
        logger.exception("Error querying MySQL tables")
        return {"success": False, "message": f"Connected, but failed to fetch schema: {str(ex)}"}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def fetch_table_columns(
    host: str,
    port: Any,
    user: str,
    password: str,
    database: str,
    table_name: str
) -> Dict[str, Any]:
    """Fetches column details for a specific table using provided credentials."""
    safe_table = sanitize_identifier(table_name)
    if not safe_table:
        return {"success": False, "message": "Invalid table name."}
    if not host or not user or not database:
        return {"success": False, "message": "Host, user, and database credentials are required."}

    conn = None
    try:
        conn = get_mysql_connection(host=host, port=port, user=user, password=password, database=database)
        with conn.cursor() as cur:
            cur.execute(f"DESCRIBE `{safe_table}`;")
            columns = cur.fetchall() or []
            col_list = [{"name": c.get("Field"), "type": c.get("Type"), "null": c.get("Null")} for c in columns]
            return {"success": True, "columns": col_list}
    except Exception as ex:
        return {"success": False, "message": str(ex)}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def fetch_mysql_data(
    host: str,
    port: Any,
    user: str,
    password: str,
    database: str,
    mode: str = "table",
    table_name: Optional[str] = None,
    custom_query: Optional[str] = None,
    limit: Optional[int] = None,
    where_clause: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Executes table extract or safe custom query using user credentials and returns (DataFrame, error_string).
    Handles type conversions (Decimals, Bytes, Times, Datetimes) for complete DataNova compatibility.
    """
    if not host or not str(host).strip():
        return None, "Host is required to fetch data."
    if not user or not str(user).strip():
        return None, "Username is required to fetch data."
    if not database or not str(database).strip():
        return None, "Database name is required to fetch data."

    safe_db = sanitize_identifier(database)
    sql_query = ""

    if mode == "table":
        safe_table = sanitize_identifier(table_name or "")
        if not safe_table:
            return None, "Please select or provide a valid table name."
        
        sql_query = f"SELECT * FROM `{safe_table}`"
        if where_clause and where_clause.strip():
            where_clean = where_clause.strip()
            # Strip leading 'where' if user typed it
            if where_clean.lower().startswith('where '):
                where_clean = where_clean[6:].strip()
            if any(k in where_clean.lower() for k in DESTRUCTIVE_SQL_KEYWORDS):
                return None, "Invalid keywords found in WHERE condition."
            sql_query += f" WHERE {where_clean}"

        if limit and int(limit) > 0:
            sql_query += f" LIMIT {int(limit)}"
    else:
        if not custom_query or not custom_query.strip():
            return None, "Please provide an SQL query to execute."
        is_safe, err_msg = is_safe_read_query(custom_query)
        if not is_safe:
            return None, err_msg
        
        sql_query = custom_query.strip().rstrip(';')
        if limit and int(limit) > 0 and 'limit' not in sql_query.lower():
            sql_query += f" LIMIT {int(limit)}"

    conn = None
    try:
        try:
            conn = get_mysql_connection(
                host=host,
                port=port,
                user=user,
                password=password,
                database=safe_db,
                timeout=20
            )
        except pymysql.err.OperationalError as op_err:
            code = op_err.args[0] if op_err.args else 0
            if code == 1045:
                return None, f"Access denied for user '{user}' (Code 1045). Please verify credentials."
            elif code == 1049:
                return None, f"Database '{database}' does not exist (Code 1049)."
            elif code == 2003:
                return None, f"Cannot connect to MySQL server at {host}:{port} (Code 2003)."
            return None, f"MySQL connection error ({code}): {op_err.args[1] if len(op_err.args) > 1 else str(op_err)}"

        with conn.cursor() as cur:
            try:
                cur.execute(sql_query)
            except pymysql.err.ProgrammingError as prog_err:
                if prog_err.args and prog_err.args[0] == 1146 and mode == "table":
                    cur.execute("SHOW TABLES;")
                    all_tbls = [list(r.values())[0] for r in (cur.fetchall() or [])]
                    for cand_tbl in all_tbls:
                        if cand_tbl.lower() == safe_table.lower():
                            safe_table = cand_tbl
                            retry_query = f"SELECT * FROM `{safe_table}`"
                            if where_clause and where_clause.strip():
                                retry_query += f" WHERE {where_clean}"
                            if limit and int(limit) > 0:
                                retry_query += f" LIMIT {int(limit)}"
                            cur.execute(retry_query)
                            break
                    else:
                        raise
                else:
                    raise

            rows = cur.fetchall()

            if not rows:
                col_names = [d[0] for d in cur.description] if cur.description else []
                df = pd.DataFrame(columns=col_names)
            else:
                df = pd.DataFrame(rows)

        # Normalize special MySQL types for DataFrame and downstream JSON/analytics pipelines
        for col in df.columns:
            if len(df) > 0 and df[col].dtype == object:
                def _normalize_cell(val):
                    if val is None or pd.isna(val):
                        return None
                    if isinstance(val, (bytes, bytearray)):
                        return val.decode('utf-8', errors='ignore')
                    if isinstance(val, (datetime.time,)):
                        return val.strftime('%H:%M:%S')
                    if isinstance(val, decimal.Decimal):
                        return float(val) if '.' in str(val) else int(val)
                    return val

                df[col] = df[col].apply(_normalize_cell)

        return df, None

    except pymysql.MySQLError as m_err:
        logger.exception("MySQL execution error")
        return None, f"MySQL Query Error: {str(m_err)}"
    except Exception as ex:
        logger.exception("Error fetching data from MySQL")
        return None, f"Data fetch failed: {str(ex)}"
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_app_db_credentials() -> Dict[str, Any]:
    """Returns local DataNova database credentials from environment variables."""
    return {
        "host": os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "localhost",
        "port": int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or 3306),
        "user": os.getenv("DB_USER") or os.getenv("MYSQLUSER") or "root",
        "password": os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or "",
        "database": os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or "DATANOVA"
    }
