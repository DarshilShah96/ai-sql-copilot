# 🤖 AI SQL Copilot

AI SQL Copilot converts business questions into SQL using an LLM, validates the SQL against a live database schema, lets you edit it manually, and can execute it directly on a database.

## What it does

This project is built for analytics workflows where users want to go from:

**business question → SQL → validation → execution → result**

instead of manually writing queries every time.

## Features

- Natural language to SQL
- CSV upload with schema inference
- SQLite database schema auto-detection
- Sidebar table preview with row counts
- Manual SQL editor
- SQL safety check for execution
- Validation against real SQLite tables and columns
- AI-assisted SQL fixing using schema + error context
- Save and load queries locally
- Download generated SQL
- Download query results as CSV

## Tech Stack

- Python
- Streamlit
- OpenAI API
- Pandas
- SQLAlchemy
- SQLite

## Project Structure

```text
sql_copilot/
├── app.py
├── create_sample_db.py
├── requirements.txt
├── README.md
├── .gitignore
├── sample.db              # local demo DB, ignored in git if needed
└── saved_queries.json     # local saved queries, ignored in git
