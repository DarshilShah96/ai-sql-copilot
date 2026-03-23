# 🤖 AI SQL Copilot

Convert business questions into SQL using AI.  
Built for analysts who want faster data access without writing complex queries manually.

---

## 🚀 Live Features

- 🔤 Natural language → SQL generation  
- 📁 CSV upload + automatic schema inference  
- 🗄️ SQLite database schema auto-detection  
- 📊 Table preview in sidebar  
- ✏️ Manual SQL editor (edit before execution)  
- ✅ SQL safety checks (only SELECT allowed)  
- 🔍 Schema validation before execution  
- ▶️ Run SQL directly on database  
- 🧠 AI-powered SQL fixing (auto-correct errors)  
- 💾 Save & load queries (local JSON storage)  

---

## 🧠 Problem It Solves

Most BI tools:
- require SQL knowledge  
- slow down non-technical users  
- separate question → query → insight  

This tool reduces friction:


Business Question → SQL → Result → Insight


---

## 🏗️ Tech Stack

- Python
- Streamlit (UI)
- OpenAI API (LLM)
- Pandas (data handling)
- SQLAlchemy (DB execution)
- SQLite (demo DB)

---

## 📂 Project Structure


sql_copilot/
│
├── app.py
├── requirements.txt
├── create_sample_db.py
├── sample.db (ignored)
├── saved_queries.json (ignored)


---

## ⚙️ Setup (Local)

### 1. Clone repo

```bash
git clone https://github.com/DarshilShah96/ai-sql-copilot
cd ai-sql-copilot
2. Install dependencies
pip3 install -r requirements.txt
3. Add API key

Create .env:

OPENAI_API_KEY=your_api_key_here
4. Run app
python3 -m streamlit run app.py
🧪 Demo Workflow

Enter DB path → sample.db

Click Auto-detect schema

Ask:

Top customers by revenue

Click Generate SQL

Edit in Manual SQL Editor

Run query

Save query

Reload from sidebar

📸 Screenshots

Add:

SQL generation

query results

manual editor + saved queries

🔮 Future Improvements

PostgreSQL / MySQL support

multi-table relationship detection

query performance optimization

user authentication

cloud DB connection

query history analytics

🧑‍💻 Author

Darshil Shah

💡 Positioning

This project demonstrates:

AI + Analytics integration

LLM-based workflow automation

real-world BI use case

full-stack thinking (UI + backend + AI)

⭐ If you found this useful

Give it a star on GitHub.
