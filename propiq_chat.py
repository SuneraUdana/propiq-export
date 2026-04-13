"""
PropIQ — RAG Chatbot module
Uses Ollama (local LLM) + CSV report data as context.
Works offline, no API key needed.
"""

import glob
import json
import pandas as pd
from datetime import datetime

COUNCIL_MAP = {
    "Fitzroy": "City of Yarra", "Collingwood": "City of Yarra",
    "Richmond": "City of Yarra", "Northcote": "City of Darebin",
    "Brunswick": "City of Moreland", "Footscray": "City of Maribyrnong",
    "Hawthorn": "City of Boroondara", "South Yarra": "City of Stonnington",
    "Prahran": "City of Stonnington", "St Kilda": "City of Port Phillip",
}

def load_latest_report() -> pd.DataFrame:
    reports = sorted(glob.glob("reports/propiq_report_*.csv"), reverse=True)
    if not reports:
        return pd.DataFrame()
    df = pd.read_csv(reports[0])
    df["council"] = df["suburb"].map(COUNCIL_MAP).fillna("Other")
    return df


def build_context(df: pd.DataFrame, question: str) -> str:
    """Build a focused data context string relevant to the question."""
    if df.empty:
        return "No data available."

    q = question.lower()

    # Suburb stats summary
    suburb_stats = df.groupby("suburb").agg(
        count=("inv_score", "count"),
        avg_score=("inv_score", "mean"),
        avg_price=("sale_price", "mean"),
        avg_yield=("yield_proxy", "mean"),
        avg_walk=("walk_score", "mean"),
        avg_school=("school_rating", "mean"),
    ).round(3).reset_index()

    # Council stats
    council_stats = df.groupby("council").agg(
        count=("inv_score", "count"),
        avg_score=("inv_score", "mean"),
        avg_price=("sale_price", "mean"),
    ).round(3).reset_index()

    # Top 10 properties
    top10 = df.nlargest(10, "inv_score")[
        ["address","suburb","council","sale_price","bedrooms",
         "bathrooms","inv_score","yield_proxy","walk_score","school_rating"]
    ].round(3)

    # Overall stats
    overall = {
        "total_listings": len(df),
        "avg_inv_score": round(df["inv_score"].mean(), 3),
        "avg_price": round(df["sale_price"].mean(), 0),
        "price_range": f"${df['sale_price'].min():,.0f} – ${df['sale_price'].max():,.0f}",
        "top_suburb_by_score": suburb_stats.nlargest(1,"avg_score")["suburb"].values[0],
        "top_council_by_score": council_stats.nlargest(1,"avg_score")["council"].values[0],
        "report_date": datetime.now().strftime("%Y-%m-%d"),
    }

    context = f"""
=== PropIQ Melbourne Property Intelligence Report ===
Date: {overall['report_date']}
Total Listings: {overall['total_listings']}
Price Range: {overall['price_range']}
Avg Investment Score: {overall['avg_inv_score']}
Avg Price: ${overall['avg_price']:,.0f}
Top Suburb (by inv_score): {overall['top_suburb_by_score']}
Top Council (by inv_score): {overall['top_council_by_score']}

=== Suburb Summary ===
{suburb_stats.to_string(index=False)}

=== Council Summary ===
{council_stats.to_string(index=False)}

=== Top 10 Properties by Investment Score ===
{top10.to_string(index=False)}
"""

    # Add price-filtered subset if question mentions budget
    import re
    amounts = re.findall(r"\$?([\d,]+)k?", q)
    for amt_str in amounts:
        amt = int(amt_str.replace(",",""))
        if amt < 10000: amt *= 1000  # e.g. "800k" → 800000
        if 300000 < amt < 5000000:
            subset = df[df["sale_price"] <= amt].nlargest(5,"inv_score")[
                ["address","suburb","sale_price","inv_score","yield_proxy"]
            ].round(3)
            if not subset.empty:
                context += f"\n=== Top Properties Under ${amt:,.0f} ===\n{subset.to_string(index=False)}\n"

    return context.strip()


def ask(question: str, df: pd.DataFrame, history: list[dict]) -> str:
    """Send question + data context to local Ollama LLM."""
    try:
        import ollama
    except ImportError:
        return "❌ Ollama not installed. Run: `pip install ollama`"

    context = build_context(df, question)

    system_prompt = """You are PropIQ Assistant, an expert Melbourne property investment analyst.
You have access to real-time property data for Melbourne suburbs.
Answer questions using ONLY the data provided in the context.
Be specific — cite suburbs, prices, scores, and councils from the data.
Keep answers concise (3-5 sentences max) unless the user asks for detail.
Format numbers clearly: prices as $X,XXX,XXX, scores to 3 decimal places.
If the data doesn't support an answer, say so honestly."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": f"Here is today's property data:\n\n{context}"},
        {"role": "assistant", "content": "I've reviewed the PropIQ data. What would you like to know?"},
    ]

    # Add conversation history (last 4 turns for context)
    for turn in history[-4:]:
        messages.append({"role": "user",      "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})

    messages.append({"role": "user", "content": question})

    try:
        response = ollama.chat(
            model="llama3.2:3b",
            messages=messages,
            options={"temperature": 0.3, "num_predict": 512},
        )
        return response["message"]["content"]
    except Exception as e:
        return f"❌ Ollama error: {e}\n\nMake sure Ollama is running: `ollama serve`"
