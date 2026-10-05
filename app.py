from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import streamlit as st

from src.charts import make_chart
from src.inference import execute_generated_query, generate_sql
from src.model import TextToSQLModel
from src.mysql_db import get_mysql_schema, list_spider_databases
from src.schema import schema_summary_from_mysql


st.set_page_config(
    page_title="QueryMind",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 QueryMind")

st.caption(
    "Schema-aware Text-to-SQL Analytics Copilot · "
    "Spider + PyTorch/FLAN-T5 + MySQL"
)


@st.cache_resource
def get_model():
    return TextToSQLModel()


# ---------------------------------------------------------
# Get available MySQL Spider databases
# ---------------------------------------------------------
try:
    databases = list_spider_databases()

except Exception as e:
    st.error(
        "Could not connect to MySQL. "
        "Check .env and ensure MySQL Server is running."
    )
    st.code(str(e))
    st.stop()


if not databases:
    st.warning(
        "No migrated Spider databases found. "
        "Run scripts/migrate_spider_to_mysql.py first."
    )
    st.stop()


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
database = st.sidebar.selectbox(
    "MySQL Spider database",
    databases,
)

st.sidebar.write("Model source:")
st.sidebar.code(get_model().source)


# ---------------------------------------------------------
# Load schema
# ---------------------------------------------------------
try:
    schema = get_mysql_schema(database)
    schema_text = schema_summary_from_mysql(schema)

except Exception as e:
    st.error(f"Could not read schema: {e}")
    st.stop()


with st.expander("View database schema"):
    st.code(schema_text, language="text")


# ---------------------------------------------------------
# User question
# ---------------------------------------------------------
question = st.text_input(
    "Ask a question about the selected database",
    placeholder="Example: How many singers are from France?",
)


# ---------------------------------------------------------
# Generate SQL and execute
# ---------------------------------------------------------
if st.button(
    "Generate & Run SQL",
    type="primary",
    disabled=not question.strip(),
):

    # STEP 1 - Generate SQL
    try:
        with st.spinner("Generating SQL..."):

            generated_query = generate_sql(
                question,
                database,
                get_model(),
            )

        # IMPORTANT:
        # Show SQL BEFORE attempting execution
        st.subheader("Generated SQL")

        st.code(
            generated_query.sql,
            language="sql",
        )

    except Exception as e:
        st.error("SQL generation or validation failed.")
        st.code(str(e))
        st.stop()

    # STEP 2 - Execute SQL
    try:
        with st.spinner("Executing query on MySQL..."):

            result = execute_generated_query(
                generated_query
            )

        st.subheader("Result")

        if result.dataframe.empty:
            st.info(
                "Query executed successfully "
                "but returned no rows."
            )

        else:
            st.dataframe(
                result.dataframe,
                use_container_width=True,
            )

            chart = make_chart(
                result.dataframe
            )

            if chart is not None:
                st.plotly_chart(
                    chart,
                    use_container_width=True,
                )

    except Exception as e:
        st.error(
            "SQL was generated successfully, "
            "but MySQL execution failed."
        )

        st.code(str(e))


st.divider()

st.caption(
    "Safety: generated SQL is validated and "
    "only read-only SELECT/CTE queries are executed."
)