# Conversational BI Dashboards (Prototype)

Generate interactive business dashboards from plain-English prompts.

## Stack
- **Frontend**: Next.js (App Router) + Plotly
- **Backend**: FastAPI + DuckDB (query uploaded CSV) + OpenRouter (text → SQL → dashboard spec)
- **Data**: Upload any CSV, or use the included sample dataset

## Prerequisites
- **Python 3.10+**
- **Node.js 20+** (includes `npm`)
- An **OpenRouter API key**

## Setup

### 1) Backend

```bash
cd E:\BIA\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
set OPENROUTER_API_KEY=YOUR_KEY_HERE
# optional
# set OPENROUTER_MODEL=google/gemini-2.0-flash-001
uvicorn app.main:app --reload --port 8000
```

Backend will be available at `http://localhost:8000`.

### 2) Frontend

```bash
cd E:\BIA\frontend
npm install
npm run dev
```

Frontend will be available at `http://localhost:3000`.

## Using the app
1. Open `http://localhost:3000`
2. Upload a CSV or click **Use sample dataset**
3. Ask a question and the app will:
   - infer schema
   - generate safe DuckDB SQL
   - run the query
   - choose chart types and render a dashboard

## Demo script (10 minutes)

Use the built-in `sample_sales.csv` dataset.

### Query 1 (basic)
**Prompt**:
“Show monthly revenue for Q3.”

### Query 2 (intermediate)
**Prompt**:
“Show me the monthly sales revenue for Q3 broken down by region and highlight the top-performing product category.”

### Query 3 (complex)
**Prompt**:
“Compare profit vs revenue by region, highlight anomalies, and limit to top 5 regions by revenue.”

**Follow-up**:
“Now filter this to only show the East Coast.”

## Notes / Limitations (prototype)
- The backend currently executes **one SQL query** and uses its result for all dashboard tiles (fast to demo; easy to extend to per-tile queries).
- Sessions are stored **in-memory** (restart backend clears sessions).

