<div align="center">
  <h1>🏠 PropIQ</h1>
  <p><strong>AI-Powered Real Estate Investment Engine & Data Pipeline</strong></p>
</div>

## 🌟 Overview
PropIQ is an automated property intelligence engine that replaces manual real estate spreadsheets. It scrapes live property listings, enriches them with NLP-extracted features (like renovations, solar, pool presence), and mathematically scores them based on yield, risk, and liquidity. 

The system includes an interactive dashboard and a **Llama-3 powered AI Analyst**, allowing users to chat directly with live market data to find undervalued properties.

## 📊 Performance Benchmarks
To validate the PropIQ scoring algorithm, we benchmarked the AI's "Top 20% Picks" against the rest of the market across 796 live properties in Melbourne.

The results mathematically prove the algorithm successfully isolates high-yield, low-risk investments:

```text
=======================================================
🚀 PROPIQ AI: ALGORITHM BENCHMARK REPORT
=======================================================
Total Properties Analyzed: 796

📊 PORTFOLIO QUALITY (Top 20% AI Picks vs Market Average)
Top 20% Yield Proxy: 0.4001  |  Market Average: 0.0408
Top 20% Risk Score:  0.2209  |  Market Average: 0.3519

✅ SUCCESS: AI isolated properties with +880.6% higher yield capacity.
✅ SUCCESS: AI reduced investment risk exposure by 59.3%.

🎯 PREDICTION ACCURACY (Real-World Outcomes)
Status: Outcomes module initializing. Waiting for first tracked sale event.
=======================================================
```

## 🏗 Architecture & Tech Stack
PropIQ is built for speed and persistence, currently deployed on Railway.
* **Backend:** FastAPI (Python)
* **Database:** SQLite (Persisted using Railway Volumes)
* **LLM Engine:** Groq (Llama-3-70b-versatile) for the AI Analyst
* **Frontend:** Vanilla HTML/JS (No complex build steps, served directly via FastAPI)
* **Data Processing:** NumPy & built-in JSON parsing for NLP enrichment

## 🚀 Key Features
1. **Automated Pipeline:** Enter a suburb, and PropIQ automatically scrapes, enriches, and scores the properties.
2. **Investment Scoring Algorithm:** Calculates an `inv_score` based on Cap Rate (Yield Proxy), liquidity (days on market), and risk.
3. **Conversational AI Analyst:** Chat with your database. Ask questions like *"Which property in Richmond under $700K has the highest investment score?"*
4. **Outcome Tracking:** Logs properties and tracks them until they are sold, calculating the Mean Absolute Percentage Error (MAPE) of the system's price predictions against the real world.

## 💻 Running Locally

1. **Clone the repo:**
   ```bash
   git clone https://github.com/sunera01/propiq-export.git
   cd propiq-export
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Environment Variables (`.env`):**
   ```env
   GROQ_API_KEY=your_groq_key
   DB_PATH=data/propiq.db
   ```

4. **Run the server:**
   ```bash
   uvicorn app:app --reload
   ```

5. **Run the Benchmark:**
   ```bash
   python propiq/benchmark.py
   ```

## 📈 Future Roadmap
- [ ] Connect Outcome Tracker to live auction clearance APIs to automatically calculate Hit Rate.
- [ ] Add Geospatial visualization to the dashboard.
- [ ] Migrate SQLite to PostgreSQL for larger dataset scaling.

---
*Disclaimer: PropIQ is built for educational and research purposes. Do not make financial decisions based solely on AI-generated scores.*
