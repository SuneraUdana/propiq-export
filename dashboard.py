import streamlit as st
import pandas as pd
import plotly.express as px
import glob

st.set_page_config(page_title="PropIQ Dashboard", layout="wide", page_icon="🏠")
st.title("🏠 PropIQ — Melbourne Property Intelligence")

reports = sorted(glob.glob("reports/propiq_report_*.csv"), reverse=True)
if not reports:
    st.error("No reports found. Run the pipeline first.")
    st.stop()

st.sidebar.header("Filters")
selected = st.sidebar.selectbox("Report Date", reports)
df = pd.read_csv(selected)

# Sidebar filters
suburbs = st.sidebar.multiselect(
    "Suburbs",
    sorted(df["suburb"].unique()),
    default=df["suburb"].unique().tolist()
)
min_score = st.sidebar.slider("Min Score", 0.0, float(df["inv_score"].max()), 0.0)
df = df[df["suburb"].isin(suburbs) & (df["inv_score"] >= min_score)]

# KPIs
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Listings", len(df))
col2.metric("Avg Inv Score", f"{df['inv_score'].mean():.3f}")
col3.metric("Avg Price", f"${df['sale_price'].mean():,.0f}")
col4.metric("Top Suburb", df.groupby("suburb")["inv_score"].mean().idxmax())

st.divider()

# Charts row 1
col1, col2 = st.columns(2)
with col1:
    fig = px.box(df, x="suburb", y="inv_score", color="suburb",
                 title="Investment Score by Suburb")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig = px.scatter(df, x="sale_price", y="inv_score", color="suburb",
                     hover_data=["address"],
                     title="Price vs Investment Score")
    st.plotly_chart(fig, use_container_width=True)

# Charts row 2
col1, col2 = st.columns(2)
with col1:
    suburb_avg = df.groupby("suburb")["inv_score"].mean().reset_index().sort_values("inv_score", ascending=False)
    fig = px.bar(suburb_avg, x="suburb", y="inv_score", color="suburb",
                 title="Avg Investment Score by Suburb")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
with col2:
    fig = px.scatter(df, x="walk_score", y="inv_score", color="suburb",
                     size="school_rating", hover_data=["address"],
                     title="Walk Score vs Investment Score")
    st.plotly_chart(fig, use_container_width=True)

# Top 20 table
st.subheader("🏆 Top 20 Properties")
st.dataframe(
    df.sort_values("inv_score", ascending=False).head(20)
      [["address","suburb","sale_price","bedrooms","bathrooms",
        "land_size_sqm","walk_score","school_rating","inv_score","rank_suburb"]]
      .reset_index(drop=True),
    use_container_width=True
)
