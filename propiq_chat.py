import glob
from datetime import datetime
import pandas as pd
import streamlit as st
from groq import Groq

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
    if df.empty:
        return "No data available."
    suburb_stats = df.groupby("suburb").agg(
        count=("inv_score","count"), avg_score=("inv_score","mean"),
        avg_price=("sale_price","mean"), avg_yield=("yield_proxy","mean"),
        avg_walk=("walk_score","mean"), avg_school=("school_rating","mean"),
        avg_risk=("risk_score","mean"),
    ).round(3).reset_index()
    council_stats = df.groupby("council").agg(
        count=("inv_score","count"), avg_score=("inv_score","mean"),
        avg_price=("sale_price","mean"), avg_yield=("yield_proxy","mean"),
        avg_risk=("risk_score","mean"),
    ).round(3).reset_index()
    top10 = df.nlargest(10,"inv_score")[
        ["address","suburb","council","sale_price","bedrooms","bathrooms",
         "inv_score","yield_proxy","walk_score","school_rating","risk_score"]
    ].round(3)
    return f"""
=== PropIQ Melbourne Property Intelligence ===
Date: {datetime.now().strftime('%Y-%m-%d')} | Listings: {len(df)}
Avg Score: {df['inv_score'].mean():.3f} | Avg Price: ${df['sale_price'].mean():,.0f}
Price Range: ${df['sale_price'].min():,.0f} – ${df['sale_price'].max():,.0f}

=== Suburb Summary ===
{suburb_stats.to_string(index=False)}

=== Council Summary ===
{council_stats.to_string(index=False)}

=== Top 10 Properties ===
{top10.to_string(index=False)}
""".strip()

def ask(question: str, df: pd.DataFrame, history: list[dict]) -> str:
    api_key = st.secrets.get("GROQ_API_KEY")
    if not api_key:
        return "❌ GROQ_API_KEY not found in Streamlit secrets."
    client = Groq(api_key=api_key)
    context = build_context(df, question)
    messages = [
        {"role": "system", "content": (
            "You are PropIQ Assistant, an expert Melbourne property investment analyst. "
            "Use only the provided data. Be concise and specific — cite suburbs, councils, "
            "prices, scores, yields, and risk. If data doesn't support a claim, say so."
        )},
        {"role": "user", "content": f"Here is today's PropIQ data:\n\n{context}"},
        {"role": "assistant", "content": "I've reviewed the PropIQ data. What would you like to know?"},
    ]
    for turn in history[-4:]:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["assistant"]})
    messages.append({"role": "user", "content": question})
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_completion_tokens=700,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Groq error: {e}"
