import os
import logging
import pymysql
from pymysql.cursors import DictCursor
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


def _get_env_fallback(host: str, user: str, password: str, database: Optional[str]) -> Tuple[str, str, str, Optional[str]]:
    """Helper to fill missing credentials with system environment defaults if available."""
    env_host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or os.getenv("MYSQL_HOST") or "127.0.0.1"
    env_user = os.getenv("DB_USER") or os.getenv("MYSQLUSER") or os.getenv("MYSQL_USER") or "root"
    env_pass = os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or os.getenv("MYSQL_PASSWORD") or ""
    env_name = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or os.getenv("MYSQL_DATABASE")

    h = str(host or "").strip() or env_host
    u = str(user or "").strip() or env_user
    p = str(password or "") if password is not None else env_pass
    d = str(database or "").strip() if database else env_name

    return h, u, p, d


def _attempt_pymysql_connect(conn_args: dict) -> pymysql.connections.Connection:
    """
    Attempts connection with fallback between 'localhost' and '127.0.0.1' for Windows/socket compatibility.
    """
    original_host = conn_args.get("host", "127.0.0.1")
    hosts_to_try = [original_host]

    if original_host.lower() == "localhost":
        hosts_to_try.append("127.0.0.1")
    elif original_host == "127.0.0.1":
        hosts_to_try.append("localhost")

    last_exc = None
    for h in hosts_to_try:
        try:
            cur_args = conn_args.copy()
            cur_args["host"] = h
            return pymysql.connect(**cur_args)
        except pymysql.OperationalError as op_ex:
            last_exc = op_ex
        except Exception as ex:
            last_exc = ex

    if last_exc:
        raise last_exc
    raise pymysql.OperationalError(0, f"Unable to connect to MySQL host {original_host}")


def test_mysql_connection(
    host: str,
    port: int = 3306,
    user: str = "root",
    password: str = "",
    database: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tests connection to a remote or local MySQL database and fetches available tables.
    """
    host, user, password, database = _get_env_fallback(host, user, password, database)

    if not host:
        return {"success": False, "message": "Host/IP address is required."}

    try:
        port = int(port) if port else 3306
    except (ValueError, TypeError):
        port = 3306

    conn_args = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "connect_timeout": 8,
        "read_timeout": 15,
        "write_timeout": 15,
        "cursorclass": DictCursor,
        "charset": "utf8mb4"
    }

    if database and str(database).strip():
        conn_args["database"] = str(database).strip()

    try:
        conn = _attempt_pymysql_connect(conn_args)
        tables = []
        databases = []

        with conn.cursor() as cursor:
            # If no specific database selected, get list of databases
            if not database or not str(database).strip():
                cursor.execute("SHOW DATABASES")
                db_rows = cursor.fetchall()
                ignore_dbs = {'information_schema', 'mysql', 'performance_schema', 'sys'}
                databases = [
                    row[list(row.keys())[0]] for row in db_rows 
                    if row[list(row.keys())[0]].lower() not in ignore_dbs
                ]
            else:
                # Case-insensitive schema query from information_schema.TABLES
                cursor.execute("""
                    SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, CREATE_TIME 
                    FROM information_schema.TABLES 
                    WHERE LOWER(TABLE_SCHEMA) = LOWER(%s) AND TABLE_TYPE = 'BASE TABLE'
                    ORDER BY TABLE_NAME ASC
                """, (database,))
                table_rows = cursor.fetchall()

                if not table_rows:
                    # Fallback to SHOW TABLES if information_schema returns empty
                    try:
                        cursor.execute("SHOW TABLES")
                        raw_tables = cursor.fetchall()
                        for r in raw_tables:
                            t_name = list(r.values())[0]
                            tables.append({
                                "name": t_name,
                                "estimated_rows": "N/A",
                                "columns_count": 0
                            })
                    except Exception:
                        pass
                else:
                    for r in table_rows:
                        t_name = r.get("TABLE_NAME")
                        est_rows = r.get("TABLE_ROWS") or 0
                        tables.append({
                            "name": t_name,
                            "estimated_rows": est_rows,
                            "created_at": str(r.get("CREATE_TIME") or "")
                        })

        conn.close()

        msg = f"Connected successfully to MySQL server at {host}:{port}"
        if database:
            msg += f" (Database: '{database}', Found {len(tables)} tables)"

        return {
            "success": True,
            "message": msg,
            "databases": databases,
            "tables": tables,
            "active_database": database or (databases[0] if databases else None)
        }

    except pymysql.OperationalError as op_err:
        err_code = op_err.args[0] if len(op_err.args) > 0 else 0
        err_msg = op_err.args[1] if len(op_err.args) > 1 else str(op_err)
        logger.warning(f"MySQL connection operational error ({err_code}): {err_msg}")
        return {
            "success": False,
            "message": f"Connection Failed: {err_msg} (Error {err_code})"
        }
    except Exception as e:
        logger.error(f"Unexpected MySQL connection error: {e}")
        return {
            "success": False,
            "message": f"Connection Error: {str(e)}"
        }


def preview_mysql_table_or_query(
    host: str,
    port: int = 3306,
    user: str = "root",
    password: str = "",
    database: str = "",
    table_name: Optional[str] = None,
    custom_query: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Fetches column metadata and sample rows from a MySQL table or SQL query for preview.
    """
    df, err = load_mysql_data_to_df(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        table_name=table_name,
        custom_query=custom_query,
        limit=limit
    )

    if err or df is None:
        return {"success": False, "message": err or "Failed to load preview data."}

    df_clean = df.fillna("")
    sample_data = df_clean.head(limit).to_dict(orient="records")

    col_info = []
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        col_info.append({
            "name": col,
            "type": dtype_str,
            "non_null_count": int(df[col].notnull().sum()),
            "null_count": int(df[col].isnull().sum())
        })

    return {
        "success": True,
        "total_columns": len(df.columns),
        "total_preview_rows": len(sample_data),
        "columns": col_info,
        "sample_data": sample_data
    }


def load_mysql_data_to_df(
    host: str,
    port: int = 3306,
    user: str = "root",
    password: str = "",
    database: str = "",
    table_name: Optional[str] = None,
    custom_query: Optional[str] = None,
    limit: int = 50000
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Executes query or table extraction on remote/local MySQL DB and returns a pandas DataFrame.
    """
    host, user, password, database = _get_env_fallback(host, user, password, database)

    if not host:
        return None, "Host/IP address is required."
    if not database:
        return None, "Database name is required."

    if not table_name and not custom_query:
        return None, "Either a table name or a custom SQL query must be provided."

    try:
        port = int(port) if port else 3306
    except (ValueError, TypeError):
        port = 3306

    conn_args = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "connect_timeout": 10,
        "read_timeout": 30,
        "write_timeout": 30,
        "charset": "utf8mb4"
    }

    try:
        conn = _attempt_pymysql_connect(conn_args)
        with conn.cursor() as cursor:
            if custom_query and custom_query.strip():
                sql_clean = custom_query.strip().rstrip(";")
                blocked_keywords = ["DROP ", "DELETE ", "TRUNCATE ", "UPDATE ", "INSERT ", "ALTER ", "GRANT "]
                upper_sql = sql_clean.upper()
                for kw in blocked_keywords:
                    if kw in upper_sql:
                        conn.close()
                        return None, f"Security violation: Direct statement '{kw.strip()}' is not permitted in MySQL Analysis mode."

                if "LIMIT" not in upper_sql:
                    sql_clean = f"{sql_clean} LIMIT {int(limit)}"
            else:
                clean_table = table_name.strip().replace("`", "")
                sql_clean = f"SELECT * FROM `{clean_table}` LIMIT {int(limit)}"

            cursor.execute(sql_clean)
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

        conn.close()

        if not columns:
            return None, "Query executed but returned no column schema."

        df = pd.DataFrame(rows, columns=columns)

        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(lambda x: x.decode('utf-8', errors='ignore') if isinstance(x, (bytes, bytearray)) else x)

        return df, None

    except pymysql.OperationalError as op_err:
        err_msg = op_err.args[1] if len(op_err.args) > 1 else str(op_err)
        logger.error(f"MySQL operational error during data fetch: {err_msg}")
        return None, f"MySQL Error: {err_msg}"
    except Exception as e:
        logger.error(f"Error fetching data from MySQL: {e}")
        return None, f"MySQL Extraction Error: {str(e)}"
