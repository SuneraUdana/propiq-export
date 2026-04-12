import streamlit as st
import pandas as pd
import plotly.express as px
import glob
import os

st.set_page_config(page_title="PropIQ Dashboard", layout="wide", page_icon="🏠")

st.title("🏠 PropIQ — Melbourne Property Intelligence")

# Load latest CSV report
reports = sorted(glob.glob("reports/propiq_report_*.csv"), reverse=True)

if not reports:
    st.error("No reports found. Run the pipeline first.")
    st.stop()

# Sidebar
st.sidebar.header("Filters")
selected = st.sidebar.selectbox("Report Date", reports)
df = pd.read_csv(selected)

suburbs = st.sidebar.multiselect(
    "Suburbs",
    sorted(df["suburb"].unique()),
    default=df["suburb"].unique().tolist()
)
min_score = st.sidebar.slider("Min Score", 0.0, float(df["score"].max()), 0.0)

df = df[df["suburb"].isin(suburbs) & (df["score"] >= min_score)]

# KPI row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Listings", len(df))
col2.metric("Avg Score", f"{df['score'].mean():.3f}")
col3.metric("Avg Price", f"${df['sale_price'].mean():,.0f}")
col4.metric("Top Suburb", df.groupby("suburb")["score"].mean().idxmax())

st.divider()

# Charts
col1, col2 = st.columns(2)
with col1:
    fig = px.box(df, x="suburb", y="score", color="suburb",
                 title="Score Distribution by Suburb")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig = px.scatter(df, x="sale_price", y="score", color="suburb",
                     hover_data=["address"],
                     title="Price vs Score")
    st.plotly_chart(fig, use_container_width=True)

# Suburb avg score bar chart
st.subheader("📊 Average Score by Suburb")
suburb_avg = df.groupby("suburb")["score"].mean().reset_index().sort_values("score", ascending=False)
fig = px.bar(suburb_avg, x="suburb", y="score", color="suburb",
             title="Average PropIQ Score by Suburb")
fig.update_layout(showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# Top 20 table
st.subheader("🏆 Top 20 Properties")
st.dataframe(
    df.sort_values("score", ascending=False).head(20)
      [["address", "suburb", "sale_price", "bedrooms", "bathrooms", "score"]]
      .reset_index(drop=True),
    use_container_width=True
)
