# 🏠 PropIQ — Autonomous Property Investment Advisor

> AI-powered pipeline that scrapes, enriches, scores and ranks Melbourne sold
> properties — then lets anyone explore the data through a conversational chatbot.

---

## Architecture (7 Layers)

```
Layer 0  Data Sources         realestate.com.au · domain.com.au · Google Maps
Layer 1  Ingestion Agent      requests + BeautifulSoup + Playwright + Pydantic
Layer 2  Storage              SQLite (dev) → PostgreSQL (prod)  5 tables
Layer 3  Enrichment Agent     CNN material · NDVI tree flag · spaCy NLP · ABS Census
Layer 4  Optimisation Engine  scipy.optimize.differential_evolution (4-weight fitness)
Layer 5  Agentic Core         Planner → Tool-Use → Reflection (LangGraph pattern)
Layer 6  Reporting & Action   HTML digest · CSV export · Email · Slack alert
Layer 7  Feedback Loop        outcome tracking → monthly DE weight retraining
```

---

## Quick Start

```bash
# 1. Clone / unzip project
cd propiq

# 2. One-command setup
bash setup.sh

# 3. Activate venv
source .venv/bin/activate

# 4. Run the full pipeline (simulated data)
python -m propiq.main

# 5. Run specific suburbs
python -m propiq.main --suburbs Fitzroy Richmond Hawthorn

# 6. Live scraping (production)
python -m propiq.main --mode scrape --suburbs Fitzroy

# 7. Start the chatbot server
python -m propiq.server
# → http://localhost:8000
```

---

## Project Structure

```
propiq/
├── propiq/
│   ├── __init__.py       Package metadata
│   ├── config.py         All tunable parameters
│   ├── storage.py        SQLite schema + CRUD
│   ├── scraper.py        Simulate or live realestate.com.au
│   ├── enrichment.py     CNN material + NDVI tree + NLP + ABS
│   ├── optimizer.py      Differential Evolution + scoring
│   ├── agent.py          Planner/Tool-Use/Reflection state machine
│   ├── reporter.py       HTML digest + CSV export
│   ├── chatbot.py        Intent → SQL → response engine
│   ├── server.py         Flask API (POST /api/chat)
│   └── main.py           CLI entry point
├── data/                 SQLite DB (auto-created)
├── reports/              Generated HTML + CSV reports
├── output/               Chatbot HTML
├── assets/               Property images cache
├── requirements.txt
├── setup.sh              One-command setup script
├── .env.example          Environment variable template
└── README.md
```

---

## Scoring Formula

```
score = w₀ × yield_proxy
      − w₁ × risk_score
      + w₂ × liquidity
      + w₃ × quality
```

Weights `w₀…w₃` are tuned each run by **Differential Evolution** (`scipy.optimize`).

| Feature | What it measures |
|---------|-----------------|
| yield_proxy | How undervalued vs suburb median |
| risk_score | Age + price + NLP negatives + tree flag |
| liquidity | Walk score / 100 |
| quality | School rating + brick bonus + NLP sentiment |

---

## Chatbot — What You Can Ask

| Question | Intent |
|----------|--------|
| "Show me the top 5 investment picks" | `top_properties` |
| "Tell me about Fitzroy" | `suburb_analysis` |
| "Compare Fitzroy vs Hawthorn" | `suburb_compare` |
| "Find brick houses in Brunswick" | `material_query` |
| "Properties with giant trees?" | `tree_query` |
| "Show properties under $900K" | `price_query` |
| "Who is the best agent?" | `agent_query` |
| "Oldest heritage properties" | `year_query` |
| "Explain how the score works" | `score_explain` |
| "Give me a dataset overview" | `stats_overview` |

---

## Production Upgrade Path

| Component | Dev | Production |
|-----------|-----|-----------|
| Database | SQLite | PostgreSQL (change `DATABASE_URL` in `.env`) |
| Scraper | Simulator | `--mode scrape` + rotating proxies |
| Material classifier | Rule-based mock | Fine-tuned ResNet-18 (`torch`) |
| NDVI | Mock | Google Maps Static API + OpenCV |
| NLP | Regex | `spacy en_core_web_sm` |
| Agent | State machine | LangGraph (`pip install langgraph`) |
| Chatbot | Rule-based | OpenAI GPT-4o (`OPENAI_API_KEY` in `.env`) |
| Server | Flask dev | `gunicorn -w 4 propiq.server:app` |
| Alerts | Console | SendGrid + Slack (`SENDGRID_API_KEY` in `.env`) |

---

*Built with Python 3.12 · scipy · spaCy · SQLite · Flask*
