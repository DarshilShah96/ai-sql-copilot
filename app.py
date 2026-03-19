import os
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        api_key = None
st.set_page_config(page_title="AI SQL Copilot", page_icon="🤖", layout="wide")

st.title("🤖 AI SQL Copilot")
st.caption("Convert business questions into SQL using optional CSV-based schema inference.")

if not api_key:
    st.error("OPENAI_API_KEY not found in Streamlit secrets or .env file")
    st.stop()

client = OpenAI(api_key=api_key)

if "history" not in st.session_state:
    st.session_state.history = []


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


col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader("Upload CSV (optional)", type=["csv"])

    inferred_schema = ""
    table_name = "sales"

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

    schema = st.text_area(
        "Schema (editable)",
        value=inferred_schema,
        placeholder="""Table: sales
Columns:
- order_id (int)
- order_date (date)
- customer_id (int)
- product_name (string)
- category (string)
- revenue (float)
- quantity (int)
- region (string)""",
        height=220
    )

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
        "Top 10 customers by revenue in last 6 months",
        "Monthly revenue trend for last 12 months",
        "Revenue by category",
        "Top 5 regions by sales",
        "Average order value by month"
    ]
    selected_sample = st.selectbox("Sample questions", sample_questions)

    if selected_sample and not question:
        question = selected_sample

    generate = st.button("Generate SQL", use_container_width=True)

if generate:
    if not question.strip():
        st.warning("Please enter a business question.")
    else:
        schema_text = schema.strip() if schema.strip() else f"Table: {table_name}\nColumns unknown"

        prompt = f"""
You are an expert analytics SQL assistant.

Convert the business question into a correct SQL query.

Instructions:
- Return valid {dialect} SQL
- Use only the schema provided
- Use the table name from the schema
- Keep SQL clean and readable
- Use meaningful aliases
- Do not include markdown fences
- After SQL, provide a short plain-English explanation

Schema:
{schema_text}

Business question:
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

            output = response.choices[0].message.content.strip()

            sql_part = output
            explanation_part = ""

            if "Explanation:" in output:
                parts = output.split("Explanation:", 1)
                sql_part = parts[0].replace("SQL:", "").strip()
                explanation_part = parts[1].strip()
            else:
                sql_part = output.replace("SQL:", "").strip()

            st.session_state.history.insert(0, {
                "question": question,
                "dialect": dialect,
                "sql": sql_part,
                "explanation": explanation_part
            })

        except Exception as e:
            st.error(f"Error: {e}")

if st.session_state.history:
    latest = st.session_state.history[0]

    st.subheader("Generated SQL")
    st.code(latest["sql"], language="sql")

    st.download_button(
        label="Download SQL",
        data=latest["sql"],
        file_name="generated_query.sql",
        mime="text/plain",
        use_container_width=True
    )

    if latest["explanation"]:
        st.subheader("Explanation")
        st.write(latest["explanation"])

    st.subheader("Recent History")
    for i, item in enumerate(st.session_state.history[:5], start=1):
        with st.expander(f"{i}. {item['question']}"):
            st.code(item["sql"], language="sql")
            if item["explanation"]:
                st.write(item["explanation"])