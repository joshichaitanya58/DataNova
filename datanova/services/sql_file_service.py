import re
import io
import os
import sqlite3
import logging
from typing import Tuple, Optional, Dict, Any, List
import pandas as pd
from datanova.services import mysql_service

logger = logging.getLogger(__name__)

SYSTEM_SQLITE_TABLES = {'sqlite_master', 'sqlite_sequence', 'sqlite_stat1'}


def _decode_file_bytes(file_bytes: bytes) -> str:
    """Safely decodes raw file bytes into string trying common SQL encodings."""
    encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1', 'utf-16', 'utf-16-le']
    for enc in encodings:
        try:
            return file_bytes.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return file_bytes.decode('utf-8', errors='ignore')


def clean_sql_for_sqlite(sql_text: str) -> str:
    """
    Sanitizes MySQL, MariaDB, and PostgreSQL dump syntax so it can be parsed and
    executed by an in-memory SQLite database.
    """
    if not sql_text:
        return ""

    # 1. Remove MySQL conditional version comments: /*!40101 ... */;
    sql = re.sub(r'/\*![\s\S]*?\*/;?', '', sql_text)

    # 2. Remove standard multi-line comments /* ... */
    sql = re.sub(r'/\*[\s\S]*?\*/', '', sql)

    # 3. Remove single-line comments (-- or #)
    sql = re.sub(r'(--|#).*?(\r?\n|$)', '\n', sql)

    # 4. Remove LOCK TABLES / UNLOCK TABLES
    sql = re.sub(r'(?:LOCK\s+TABLES\s+[^;]+;|UNLOCK\s+TABLES\s*;)', '', sql, flags=re.IGNORECASE)

    # 5. Remove SET statements and transaction boundaries
    sql = re.sub(r'SET\s+[^;]+;', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'(?:START\s+TRANSACTION|COMMIT|ROLLBACK)\s*;', '', sql, flags=re.IGNORECASE)

    # 6. Remove DROP TABLE IF EXISTS statements so table creation proceeds cleanly
    # (Optional: keep if needed, but in fresh :memory: db it's safe to keep)

    # 7. Strip MySQL table options at the end of CREATE TABLE statements
    # e.g., ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci AUTO_INCREMENT=100;
    sql = re.sub(
        r'\)\s*(?:ENGINE|DEFAULT\s+CHARSET|COLLATE|AUTO_INCREMENT|ROW_FORMAT|COMMENT)\s*=[^;]+;',
        ');',
        sql,
        flags=re.IGNORECASE
    )
    sql = re.sub(
        r'\)\s*(?:ENGINE|DEFAULT\s+CHARSET|COLLATE|AUTO_INCREMENT|ROW_FORMAT)\s*[^;]*;',
        ');',
        sql,
        flags=re.IGNORECASE
    )

    # 8. Clean MySQL column attributes inside CREATE TABLE
    sql = re.sub(r'\bAUTO_INCREMENT\b', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\b(UNSIGNED|ZEROFILL)\b', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\b(ON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\(\d*\))?)', '', sql, flags=re.IGNORECASE)

    # 9. Normalize data types for SQLite
    sql = re.sub(r'\bint\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\btinyint\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bsmallint\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bmediumint\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bbigint\s*\(\d+\)', 'INTEGER', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\b(mediumtext|longtext|enum\([^)]+\)|set\([^)]+\))', 'TEXT', sql, flags=re.IGNORECASE)

    # 10. Strip MySQL INDEX / KEY definitions that SQLite does not support inside CREATE TABLE
    # e.g., KEY `idx_name` (`col`), UNIQUE KEY `uniq_name` (`col`)
    sql = re.sub(r',\s*(?:UNIQUE\s+)?KEY\s+`?\w+`?\s*\([^)]+\)', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r',\s*CONSTRAINT\s+`?\w+`?\s+FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+[^)]+\)', '', sql, flags=re.IGNORECASE)

    return sql


def _fallback_parse_inserts(raw_sql: str) -> Optional[Tuple[pd.DataFrame, str]]:
    """
    Fallback regex parser for raw SQL files with INSERT INTO statements when SQLite
    cannot parse complex DDL directly.
    """
    insert_pattern = re.compile(
        r'INSERT\s+INTO\s+[`"]?([a-zA-Z0-9_]+)[`"]?\s*(?:\(([^)]+)\))?\s*VALUES\s*(.+?);',
        re.IGNORECASE | re.DOTALL
    )
    inserts = insert_pattern.findall(raw_sql)
    if not inserts:
        return None

    tables_data: Dict[str, Dict[str, Any]] = {}
    for tbl_name, cols_str, values_block in inserts:
        cols = [c.strip().strip('`"\'') for c in cols_str.split(',')] if cols_str else None
        tuple_pattern = re.compile(r'\((.*?)\)(?:,|$)', re.DOTALL)
        row_tuples = tuple_pattern.findall(values_block)
        rows = []
        for r_str in row_tuples:
            items = []
            in_quote = False
            quote_char = ''
            current = []
            for char in r_str:
                if char in ("'", '"') and not in_quote:
                    in_quote = True
                    quote_char = char
                elif char == quote_char and in_quote:
                    in_quote = False
                elif char == ',' and not in_quote:
                    items.append("".join(current).strip().strip("'\""))
                    current = []
                    continue
                current.append(char)
            if current:
                items.append("".join(current).strip().strip("'\""))

            cleaned_items = [None if str(it).upper() == 'NULL' else it for it in items]
            if cleaned_items:
                rows.append(cleaned_items)

        if tbl_name not in tables_data:
            tables_data[tbl_name] = {'cols': cols, 'rows': []}
        tables_data[tbl_name]['rows'].extend(rows)

    if not tables_data:
        return None

    # Pick the table with the most rows
    sorted_tables = sorted(tables_data.items(), key=lambda kv: len(kv[1]['rows']), reverse=True)
    chosen_name, chosen_dict = sorted_tables[0]
    rows = chosen_dict['rows']
    cols = chosen_dict['cols']

    if rows:
        num_cols = max(len(r) for r in rows)
        if not cols or len(cols) != num_cols:
            cols = [f"column_{i+1}" for i in range(num_cols)]
        df = pd.DataFrame(rows, columns=cols)
        # Attempt to auto-infer numeric types
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass
        return df, chosen_name

    return None


def parse_sql_file_to_dataframe(
    file_bytes: bytes,
    filename: str = ""
) -> Tuple[Optional[pd.DataFrame], str, Optional[str]]:
    """
    Main entrypoint: parses uploaded .sql file bytes into an analytics-ready DataFrame.
    Returns: (df, table_name_or_source, error_message)
    """
    if not file_bytes:
        return None, "", "The uploaded .sql file is completely empty."

    sql_text = _decode_file_bytes(file_bytes)
    if not sql_text.strip():
        return None, "", "The uploaded .sql file does not contain any readable text or SQL statements."

    raw_sql = sql_text.strip()
    base_name = os.path.splitext(os.path.basename(filename))[0] if filename else ""

    # Detect standalone queries
    statements = [s.strip() for s in re.split(r';(?:\s*[\r\n]|\s*$)', raw_sql) if s.strip()]
    select_stmts = [s for s in statements if re.match(r'^(?:WITH\s+.+?\s+)?SELECT\b', s, re.IGNORECASE | re.DOTALL)]

    # -------------------------------------------------------------
    # Strategy 1: SQLite In-Memory Execution (DDL + DML + SELECT)
    # -------------------------------------------------------------
    cleaned_sql = clean_sql_for_sqlite(raw_sql)
    con = None
    try:
        con = sqlite3.connect(':memory:')
        con.executescript(cleaned_sql)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [r[0] for r in (cur.fetchall() or []) if r[0] not in SYSTEM_SQLITE_TABLES]

        if tables:
            # If the SQL file had an ending SELECT query, execute it on the in-memory tables!
            if select_stmts:
                try:
                    query_df = pd.read_sql_query(select_stmts[-1], con)
                    if not query_df.empty:
                        con.close()
                        return query_df, "sql_query_result", None
                except Exception:
                    pass

            # Count rows for each table to select the most relevant data table
            table_stats: List[Tuple[str, int]] = []
            for t in tables:
                try:
                    cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                    cnt = cur.fetchone()[0]
                    table_stats.append((t, cnt))
                except Exception:
                    table_stats.append((t, 0))

            table_stats.sort(key=lambda x: x[1], reverse=True)
            non_empty_tables = [t for t, cnt in table_stats if cnt > 0]

            selected_table = None
            if base_name:
                clean_target = re.sub(r'[^a-zA-Z0-9_]', '', base_name).lower()
                for t, cnt in table_stats:
                    if t.lower() == clean_target and cnt > 0:
                        selected_table = t
                        break

            if not selected_table and non_empty_tables:
                selected_table = non_empty_tables[0]
            elif not selected_table and table_stats:
                selected_table = table_stats[0][0]

            if selected_table:
                df = pd.read_sql_query(f'SELECT * FROM "{selected_table}"', con)
                con.close()
                if not df.empty:
                    return df, selected_table, None
        con.close()
    except Exception as ex:
        logger.warning(f"SQLite in-memory SQL execution exception: {ex}")
        if con:
            try:
                con.close()
            except Exception:
                pass

    # -------------------------------------------------------------
    # Strategy 2: Fallback Regex Parser for Raw INSERT Statements
    # -------------------------------------------------------------
    fallback_res = _fallback_parse_inserts(raw_sql)
    if fallback_res:
        df, tbl_name = fallback_res
        if not df.empty:
            return df, tbl_name, None

    # -------------------------------------------------------------
    # Strategy 3: Standalone SELECT Query (Execute via Platform MySQL)
    # -------------------------------------------------------------
    if len(statements) <= 2 and select_stmts:
        query_to_run = select_stmts[-1]
        try:
            creds = mysql_service.get_app_db_credentials()
            df, query_err = mysql_service.fetch_mysql_data(
                host=creds['host'],
                port=creds['port'],
                user=creds['user'],
                password=creds['password'],
                database=creds['database'],
                mode='query',
                custom_query=query_to_run,
                limit=10000
            )
            if df is not None and not df.empty:
                return df, "query_result", None
            if query_err:
                return None, "", f"The .sql file contains a query that could not be executed against the database: {query_err}"
        except Exception as q_ex:
            logger.warning(f"Failed to execute standalone SQL query against platform DB: {q_ex}")

    return (
        None,
        "",
        "Unable to extract dataset records from the .sql file. "
        "Please ensure the file contains valid CREATE TABLE and INSERT INTO statements with data rows."
    )
