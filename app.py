import os
import re
import json
import sqlite3
import pandas as pd
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st
from sqlalchemy import create_engine, text

load_dotenv()

SAVE_FILE = "saved_queries.json"

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        api_key = None

st.set_page_config(page_title="AI SQL Copilot", page_icon="🤖", layout="wide")

st.title("🤖 AI SQL Copilot")
st.caption("Convert business questions into SQL using CSV or database schema.")

if not api_key:
    st.error("OPENAI_API_KEY not found in Streamlit secrets or .env file")
    st.stop()

client = OpenAI(api_key=api_key)

if "history" not in st.session_state:
    st.session_state.history = []

if "schema_text" not in st.session_state:
    st.session_state.schema_text = ""

if "db_tables" not in st.session_state:
    st.session_state.db_tables = []

if "last_error" not in st.session_state:
    st.session_state.last_error = ""

if "last_validation_error" not in st.session_state:
    st.session_state.last_validation_error = ""

if "sql_editor_value" not in st.session_state:
    st.session_state.sql_editor_value = ""


def load_saved_queries():
    if not os.path.exists(SAVE_FILE):
        return []
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_query_to_file(query_obj):
    data = load_saved_queries()
    data.insert(0, query_obj)

    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def infer_schema_from_df(df: pd.DataFrame, table_name: str = "uploaded_data") -> str:
    lines = [f"Table: {table_name}", "Columns:"]
    for col, dtype in df.dtypes.items():
        lines.append(f"- {col} ({dtype})")
    return "\n".join(lines)


def load_csv(file) -> pd.DataFrame:
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            file.seek(0)
            return pd.read_csv(file, encoding=encoding)
        except Exception:
            continue
    raise Exception("Unable to read CSV with supported encodings: utf-8, latin-1, cp1252")


def is_safe_query(sql_query: str) -> bool:
    cleaned = sql_query.strip().lower()
    blocked = ["insert", "update", "delete", "drop", "alter", "truncate", "create"]
    return cleaned.startswith("select") and not any(word in cleaned for word in blocked)


def get_engine(db_type: str, db_path: str):
    if db_type == "SQLite":
        return create_engine(f"sqlite:///{db_path}")
    raise ValueError("Unsupported database type")


def run_sql_query(engine, sql_query: str) -> pd.DataFrame:
    with engine.connect() as conn:
        result = conn.execute(text(sql_query))
        rows = result.fetchall()
        columns = result.keys()
        return pd.DataFrame(rows, columns=columns)


def infer_schema_from_sqlite_db(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cur.fetchall()]

    lines = []

    for table in tables:
        lines.append(f"Table: {table}")
        cur.execute(f'PRAGMA table_info("{table}")')
        columns = cur.fetchall()

        for col in columns:
            col_name = col[1]
            col_type = col[2] if col[2] else "TEXT"
            lines.append(f"- {col_name} ({col_type})")

        lines.append("")

    conn.close()
    return "\n".join(lines).strip()


def get_sqlite_tables(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables


def get_sqlite_table_preview(db_path: str, table_name: str, limit: int = 5) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = f'SELECT * FROM "{table_name}" LIMIT {limit}'
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def get_sqlite_table_count(db_path: str, table_name: str) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_sqlite_schema_map(db_path: str) -> dict:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cur.fetchall()]

    schema_map = {}
    for table in tables:
        cur.execute(f'PRAGMA table_info("{table}")')
        cols = [row[1] for row in cur.fetchall()]
        schema_map[table.lower()] = set(col.lower() for col in cols)

    conn.close()
    return schema_map


def extract_tables_from_sql(sql_query: str) -> set:
    pattern = r'(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    return set(match.lower() for match in re.findall(pattern, sql_query, flags=re.IGNORECASE))


def extract_aliases_from_sql(sql_query: str) -> dict:
    pattern = r'(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)(?:\s+([a-zA-Z_][a-zA-Z0-9_]*))?'
    alias_map = {}
    for table, alias in re.findall(pattern, sql_query, flags=re.IGNORECASE):
        table_l = table.lower()
        alias_map[table_l] = table_l
        if alias:
            alias_map[alias.lower()] = table_l
    return alias_map


def extract_qualified_columns(sql_query: str) -> list[tuple[str, str]]:
    pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)'
    return [(a.lower(), c.lower()) for a, c in re.findall(pattern, sql_query)]


def validate_sql_against_sqlite(sql_query: str, db_path: str) -> tuple[bool, str]:
    schema_map = get_sqlite_schema_map(db_path)
    tables = extract_tables_from_sql(sql_query)
    alias_map = extract_aliases_from_sql(sql_query)
    qualified_cols = extract_qualified_columns(sql_query)

    for table in tables:
        if table not in schema_map:
            return False, f"Unknown table referenced: {table}"

    for alias, col in qualified_cols:
        if alias not in alias_map:
            return False, f"Unknown table alias referenced: {alias}"
        real_table = alias_map[alias]
        if real_table not in schema_map:
            return False, f"Unknown table referenced through alias: {real_table}"
        if col not in schema_map[real_table]:
            return False, f"Unknown column '{col}' in table '{real_table}'"

    return True, "SQL validated successfully"


def parse_sql_response(output: str) -> tuple[str, str]:
    sql_part = output
    explanation_part = ""

    if "Explanation:" in output:
        parts = output.split("Explanation:", 1)
        sql_part = parts[0].replace("SQL:", "").strip()
        explanation_part = parts[1].strip()
    else:
        sql_part = output.replace("SQL:", "").strip()

    return sql_part, explanation_part


def fix_sql_with_llm(
    bad_sql: str,
    error_msg: str,
    schema_text: str,
    dialect: str,
    question: str
) -> tuple[str, str]:
    prompt = f"""
You are an expert analytics SQL assistant.

A previously generated SQL query failed validation or execution.

Your job:
Repair the SQL so it works with the provided schema and business question.

CRITICAL RULES:
- Return valid {dialect} SQL
- Use ONLY the tables and columns in the schema
- Preserve the original business intent
- Automatically create JOINs when needed
- Prefer INNER JOIN unless the question implies otherwise
- Do not include markdown fences
- Do not invent tables or columns
- Return only fixed SQL plus a short explanation

Schema:
{schema_text}

Business Question:
{question}

Broken SQL:
{bad_sql}

Error:
{error_msg}

Output format:

SQL:
<fixed_query>

Explanation:
<short explanation of what was fixed>
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You repair SQL queries using the given schema and database error."
            },
            {"role": "user", "content": prompt}
        ]
    )
    return parse_sql_response(response.choices[0].message.content.strip())


st.sidebar.header("Database")
db_type = st.sidebar.selectbox("Database type", ["SQLite"])
db_path = st.sidebar.text_input("SQLite DB path", value="sample.db")
run_query = st.sidebar.checkbox("Run generated SQL on database")
load_db_schema = st.sidebar.button("Auto-detect schema from DB")

if load_db_schema:
    try:
        if db_type == "SQLite":
            st.session_state.schema_text = infer_schema_from_sqlite_db(db_path)
            st.session_state.db_tables = get_sqlite_tables(db_path)
            st.sidebar.success("Schema loaded from database")
        else:
            st.sidebar.error("Auto-detect currently supports SQLite only")
    except Exception as e:
        st.sidebar.error(f"Schema detection error: {e}")

if db_type == "SQLite":
    try:
        tables_now = get_sqlite_tables(db_path)
        if tables_now:
            st.session_state.db_tables = tables_now
    except Exception:
        pass

saved_queries = load_saved_queries()
st.sidebar.subheader("Saved Queries")

if saved_queries:
    selected_saved_query = st.sidebar.selectbox(
        "Select saved query",
        [q["name"] for q in saved_queries]
    )

    selected_saved_obj = next(q for q in saved_queries if q["name"] == selected_saved_query)

    if st.sidebar.button("Load Query"):
        loaded_sql = selected_saved_obj.get("sql", "")
        loaded_question = selected_saved_obj.get("question", "")
        loaded_schema = selected_saved_obj.get("schema_text", "")
        loaded_dialect = selected_saved_obj.get("dialect", "ANSI SQL")

        st.session_state.sql_editor_value = loaded_sql
        st.session_state.history.insert(0, {
            "question": loaded_question,
            "dialect": loaded_dialect,
            "schema_text": loaded_schema,
            "sql": loaded_sql,
            "explanation": selected_saved_obj.get("explanation", ""),
            "is_safe": is_safe_query(loaded_sql)
        })
        st.rerun()

if st.session_state.db_tables:
    st.sidebar.subheader("Database Tables")
    selected_table = st.sidebar.selectbox("Preview table", st.session_state.db_tables)

    try:
        row_count = get_sqlite_table_count(db_path, selected_table)
        st.sidebar.caption(f"Rows: {row_count}")

        preview_df = get_sqlite_table_preview(db_path, selected_table, limit=5)
        st.sidebar.dataframe(preview_df, use_container_width=True)
    except Exception as e:
        st.sidebar.error(f"Preview error: {e}")

col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader("Upload CSV (optional)", type=["csv"])

    inferred_schema = ""

    if uploaded_file is not None:
        try:
            df = load_csv(uploaded_file)
            table_name = uploaded_file.name.replace(".csv", "").replace(" ", "_").lower()
            inferred_schema = infer_schema_from_df(df, table_name=table_name)

            st.success("CSV loaded successfully")
            st.subheader("Preview")
            st.dataframe(df.head(10), use_container_width=True)

        except Exception as e:
            st.error(f"CSV load error: {e}")

    default_schema = st.session_state.schema_text or inferred_schema

    schema = st.text_area(
        "Schema (editable)",
        value=default_schema,
        placeholder="""Example:

Table: orders
- order_id
- customer_id
- order_date
- revenue

Table: customers
- customer_id
- customer_name
- region""",
        height=220
    )

    st.info("Tip: Use common keys like customer_id, product_id, order_id to enable automatic joins.")

    question = st.text_area(
        "Business question",
        placeholder="Top 5 products by revenue in last 6 months",
        height=120
    )

with col2:
    dialect = st.selectbox(
        "SQL dialect",
        ["ANSI SQL", "PostgreSQL", "MySQL", "SQL Server", "Snowflake", "BigQuery"]
    )

    sample_questions = [
        "",
        "Top customers by revenue",
        "Revenue by region",
        "Monthly revenue trend",
        "Top 5 regions by sales",
        "Average revenue by customer"
    ]
    selected_sample = st.selectbox("Sample questions", sample_questions)

    if selected_sample and not question:
        question = selected_sample

    generate = st.button("Generate SQL", use_container_width=True)

if generate:
    st.session_state.last_error = ""
    st.session_state.last_validation_error = ""

    if not question.strip():
        st.warning("Please enter a business question.")
    elif not schema.strip():
        st.error("Please provide schema before generating SQL.")
    else:
        schema_text = schema.strip()

        prompt = f"""
You are an expert analytics SQL assistant.

Your job:
Convert the business question into a correct SQL query.

CRITICAL RULES:
- Use ONLY the tables and columns provided
- Detect relationships using column names such as customer_id, order_id, product_id
- Automatically create JOINs when needed
- Prefer INNER JOIN unless the question implies otherwise
- Use clean table aliases
- Avoid unnecessary joins
- Return valid {dialect} SQL
- Do not include markdown fences
- Do not invent columns
- After SQL, give a short explanation

Schema:
{schema_text}

Business Question:
{question}

Output format:

SQL:
<query>

Explanation:
<short explanation>
"""

        try:
            with st.spinner("Generating SQL..."):
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You generate accurate analytics SQL from schema and business questions."
                        },
                        {"role": "user", "content": prompt}
                    ]
                )

            sql_part, explanation_part = parse_sql_response(
                response.choices[0].message.content.strip()
            )

            st.session_state.history.insert(0, {
                "question": question,
                "dialect": dialect,
                "schema_text": schema_text,
                "sql": sql_part,
                "explanation": explanation_part,
                "is_safe": is_safe_query(sql_part)
            })
            st.session_state.sql_editor_value = sql_part

        except Exception as e:
            st.error(f"Error: {e}")

if st.session_state.history:
    latest = st.session_state.history[0]

    if not st.session_state.sql_editor_value:
        st.session_state.sql_editor_value = latest["sql"]

    st.subheader("Generated SQL")
    st.code(latest["sql"], language="sql")

    st.subheader("Manual SQL Editor")
    edited_sql = st.text_area(
        "Edit SQL before validate/run/fix",
        value=st.session_state.sql_editor_value,
        height=220,
        key="manual_sql_editor"
    )

    editor_col1, editor_col2 = st.columns(2)

    with editor_col1:
        if st.button("Use Edited SQL", use_container_width=True):
            latest["sql"] = edited_sql
            latest["is_safe"] = is_safe_query(edited_sql)
            st.session_state.history[0] = latest
            st.session_state.sql_editor_value = edited_sql
            st.rerun()

    with editor_col2:
        if st.button("Reset to Generated SQL", use_container_width=True):
            st.session_state.sql_editor_value = latest["sql"]
            st.rerun()

    st.subheader("Save Query")
    query_name = st.text_input("Query name")

    if st.button("Save Query", use_container_width=True):
        if not query_name.strip():
            st.warning("Enter a query name")
        else:
            query_obj = {
                "name": query_name,
                "question": latest["question"],
                "sql": latest["sql"],
                "schema_text": latest.get("schema_text", ""),
                "dialect": latest.get("dialect", "ANSI SQL"),
                "explanation": latest.get("explanation", ""),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            save_query_to_file(query_obj)
            st.success("Query saved")

    if latest["is_safe"]:
        st.success("Safety check passed: only SELECT-style SQL detected.")
    else:
        st.error("Safety check failed: query contains non-safe SQL keywords.")

    action_col1, action_col2 = st.columns(2)

    with action_col1:
        if latest["is_safe"]:
            st.download_button(
                label="Download SQL",
                data=latest["sql"],
                file_name="generated_query.sql",
                mime="text/plain",
                use_container_width=True
            )

    with action_col2:
        fix_clicked = st.button("Fix SQL", use_container_width=True)

    if fix_clicked:
        if not latest["question"].strip():
            st.error("No question found for this SQL.")
        else:
            combined_error = st.session_state.last_validation_error or st.session_state.last_error
            if not combined_error:
                combined_error = "General SQL correction requested."

            try:
                with st.spinner("Fixing SQL..."):
                    fixed_sql, fixed_explanation = fix_sql_with_llm(
                        bad_sql=latest["sql"],
                        error_msg=combined_error,
                        schema_text=latest["schema_text"],
                        dialect=latest["dialect"],
                        question=latest["question"]
                    )

                latest["sql"] = fixed_sql
                latest["explanation"] = fixed_explanation
                latest["is_safe"] = is_safe_query(fixed_sql)
                st.session_state.history[0] = latest
                st.session_state.sql_editor_value = fixed_sql
                st.session_state.last_error = ""
                st.session_state.last_validation_error = ""
                st.rerun()

            except Exception as e:
                st.error(f"Fix SQL error: {e}")

    if run_query:
        if not latest["is_safe"]:
            st.session_state.last_validation_error = "Only safe SELECT queries can be executed."
            st.error("Only safe SELECT queries can be executed.")
        else:
            try:
                if db_type == "SQLite":
                    is_valid, validation_msg = validate_sql_against_sqlite(latest["sql"], db_path)
                    if not is_valid:
                        st.session_state.last_validation_error = validation_msg
                        st.error(f"Validation failed: {validation_msg}")
                    else:
                        st.session_state.last_validation_error = ""
                        st.success("Validation passed against database schema.")
                        engine = get_engine(db_type, db_path)
                        result_df = run_sql_query(engine, latest["sql"])

                        st.subheader("Query Results")
                        st.dataframe(result_df, use_container_width=True)

                        csv_data = result_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label="Download Results CSV",
                            data=csv_data,
                            file_name="query_results.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                else:
                    engine = get_engine(db_type, db_path)
                    result_df = run_sql_query(engine, latest["sql"])

                    st.subheader("Query Results")
                    st.dataframe(result_df, use_container_width=True)

            except Exception as e:
                st.session_state.last_error = str(e)
                st.error(f"SQL execution error: {e}")

    if latest["explanation"]:
        st.subheader("Explanation")
        st.write(latest["explanation"])

    st.subheader("Recent History")
    for i, item in enumerate(st.session_state.history[:5], start=1):
        with st.expander(f"{i}. {item['question']}"):
            st.code(item["sql"], language="sql")
            st.caption("Safety: Passed" if item.get("is_safe") else "Safety: Failed")
            if item["explanation"]:
                st.write(item["explanation"])