import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import io
import numpy as np

st.set_page_config(page_title="PropIQ Dashboard", layout="wide", page_icon="🏠")

COUNCIL_MAP = {
    "Fitzroy":     "City of Yarra",
    "Collingwood": "City of Yarra",
    "Richmond":    "City of Yarra",
    "Northcote":   "City of Darebin",
    "Brunswick":   "City of Moreland",
    "Footscray":   "City of Maribyrnong",
    "Hawthorn":    "City of Boroondara",
    "South Yarra": "City of Stonnington",
    "Prahran":     "City of Stonnington",
    "St Kilda":    "City of Port Phillip",
}

SUBURB_COORDS = {
    "Fitzroy":     (-37.7988, 144.9784),
    "Collingwood": (-37.8044, 144.9880),
    "Richmond":    (-37.8182, 144.9993),
    "Northcote":   (-37.7714, 144.9997),
    "Brunswick":   (-37.7664, 144.9618),
    "Footscray":   (-37.8008, 144.8997),
    "Hawthorn":    (-37.8220, 145.0334),
    "South Yarra": (-37.8393, 144.9930),
    "Prahran":     (-37.8497, 144.9929),
    "St Kilda":    (-37.8676, 144.9810),
}

st.markdown("""
<style>
  div[data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; }
</style>
""", unsafe_allow_html=True)

reports = sorted(glob.glob("reports/propiq_report_*.csv"), reverse=True)
if not reports:
    st.error("No reports found. Run the pipeline first.")
    st.stop()

@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df["council"] = df["suburb"].map(COUNCIL_MAP).fillna("Other")
    df["lat"] = df["suburb"].map(lambda s: SUBURB_COORDS.get(s, (-37.81, 144.96))[0])
    df["lng"] = df["suburb"].map(lambda s: SUBURB_COORDS.get(s, (-37.81, 144.96))[1])
    df["badges"] = ""
    if "yield_proxy" in df.columns:
        df.loc[df["yield_proxy"] > df["yield_proxy"].quantile(0.75), "badges"] += "🔥 "
    if "tree_flag" in df.columns:
        df.loc[df["tree_flag"] == True, "badges"] += "🌳 "
    if "walk_score" in df.columns:
        df.loc[df["walk_score"] >= 80, "badges"] += "🚶 "
    if "school_rating" in df.columns:
        df.loc[df["school_rating"] >= 8, "badges"] += "🏫 "
    if "risk_score" in df.columns:
        df.loc[df["risk_score"] <= df["risk_score"].quantile(0.25), "badges"] += "🛡️ "
    return df

st.markdown("## 🏠 PropIQ — Melbourne Property Intelligence")
st.caption("Agentic property scoring across Melbourne suburbs")

with st.sidebar:
    st.title("PropIQ Filters")
    selected_report = st.selectbox("📅 Report Date", reports,
                                   format_func=lambda x: x.split("_")[-1].replace(".csv",""))
    df = load_data(selected_report)
    st.divider()
    all_councils = sorted(df["council"].unique())
    sel_councils = st.multiselect("🏛️ Council", all_councils, default=all_councils)
    available_suburbs = sorted(df[df["council"].isin(sel_councils)]["suburb"].unique())
    sel_suburbs = st.multiselect("📍 Suburb", available_suburbs, default=available_suburbs)
    st.divider()
    pmin, pmax = int(df["sale_price"].min()), int(df["sale_price"].max())
    price_range = st.slider("💰 Price Range ($)", pmin, pmax, (pmin, pmax), step=10000)
    bed_options = sorted(df["bedrooms"].dropna().unique().astype(int))
    sel_beds = st.multiselect("🛏️ Bedrooms", bed_options, default=bed_options)
    type_options = sorted(df["house_type"].dropna().unique())
    sel_types = st.multiselect("🏡 Property Type", type_options, default=type_options)
    min_score = st.slider("⭐ Min Inv Score", 0.0, float(df["inv_score"].max()), 0.0, step=0.01)
    st.divider()
    if st.button("🔄 Reset Filters"):
        st.rerun()

fdf = df[
    df["suburb"].isin(sel_suburbs) &
    df["sale_price"].between(price_range[0], price_range[1]) &
    df["bedrooms"].isin(sel_beds) &
    df["house_type"].isin(sel_types) &
    (df["inv_score"] >= min_score)
]

st.caption(f"Showing **{len(fdf)}** of **{len(df)}** listings")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("🏘️ Listings",   len(fdf))
k2.metric("⭐ Avg Score",  f"{fdf['inv_score'].mean():.3f}" if len(fdf) else "—")
k3.metric("💰 Avg Price",  f"${fdf['sale_price'].mean():,.0f}" if len(fdf) else "—")
k4.metric("🏆 Top Suburb", fdf.groupby("suburb")["inv_score"].mean().idxmax() if len(fdf) else "—")
k5.metric("🏛️ Top Council",fdf.groupby("council")["inv_score"].mean().idxmax() if len(fdf) else "—")

st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview", "🗺️ Map", "🏛️ Council View", "🏆 Top Properties", "⚖️ Compare"
])

# ── TAB 1 Overview ──────────────────────────────────────────────────────────
with tab1:
    c1, c2 = st.columns(2)
    with c1:
        fig = px.box(fdf, x="suburb", y="inv_score", color="suburb",
                     title="Investment Score by Suburb")
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.scatter(fdf, x="sale_price", y="inv_score", color="suburb",
                         hover_data=["address","badges"], title="Price vs Investment Score")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    c3, c4 = st.columns(2)
    with c3:
        fig = px.scatter(fdf, x="walk_score", y="inv_score", color="suburb",
                         size="school_rating", hover_data=["address"],
                         title="Walkability vs Score (size = school rating)")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        fig = px.histogram(fdf, x="sale_price", color="suburb", nbins=30,
                           title="Price Distribution", barmode="overlay")
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

# ── TAB 2 Map ───────────────────────────────────────────────────────────────
with tab2:
    st.subheader("🗺️ Property Map — Melbourne")
    if len(fdf) == 0:
        st.warning("No properties match current filters.")
    else:
        map_df = fdf.copy()
        map_df["lat"] = map_df["lat"] + np.random.uniform(-0.003, 0.003, len(map_df))
        map_df["lng"] = map_df["lng"] + np.random.uniform(-0.003, 0.003, len(map_df))
        fig = px.scatter_mapbox(
            map_df, lat="lat", lon="lng",
            color="inv_score", size="inv_score",
            hover_name="address",
            hover_data={"suburb":True,"sale_price":True,"inv_score":True,
                        "council":True,"badges":True,"lat":False,"lng":False},
            color_continuous_scale="RdYlGn",
            size_max=18, zoom=12, mapbox_style="open-street-map",
            title="Properties coloured & sized by Investment Score"
        )
        fig.update_layout(height=600, margin={"r":0,"t":40,"l":0,"b":0})
        st.plotly_chart(fig, use_container_width=True)

# ── TAB 3 Council ───────────────────────────────────────────────────────────
with tab3:
    st.subheader("🏛️ Council (LGA) Intelligence")
    council_stats = fdf.groupby("council").agg(
        listings  =("inv_score","count"),
        avg_score =("inv_score","mean"),
        avg_price =("sale_price","mean"),
        avg_yield =("yield_proxy","mean"),
        avg_walk  =("walk_score","mean"),
        avg_school=("school_rating","mean"),
    ).reset_index().sort_values("avg_score", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(council_stats, x="council", y="avg_score", color="council",
                     title="Avg Investment Score by Council", text_auto=".3f")
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(council_stats, x="council", y="avg_price", color="council",
                     title="Avg Sale Price by Council")
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Council Profile Radar")
    metrics = ["avg_score","avg_yield","avg_walk","avg_school"]
    labels  = ["Inv Score","Yield","Walk Score","School Rating"]
    fig = go.Figure()
    for _, row in council_stats.iterrows():
        normed = [(row[m]-council_stats[m].min())/(council_stats[m].max()-council_stats[m].min()+1e-9)
                  for m in metrics]
        normed += normed[:1]
        fig.add_trace(go.Scatterpolar(r=normed, theta=labels+[labels[0]],
                                      name=row["council"], fill="toself", opacity=0.5))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,1])),
                      height=450, title="Normalised Council Profile")
    st.plotly_chart(fig, use_container_width=True)

    display = council_stats.copy()
    display.columns = ["Council","Listings","Avg Score","Avg Price ($)",
                        "Avg Yield","Avg Walk Score","Avg School Rating"]
    display["Avg Price ($)"] = display["Avg Price ($)"].apply(lambda x: f"${x:,.0f}")
    display["Avg Score"]     = display["Avg Score"].apply(lambda x: f"{x:.3f}")
    st.dataframe(display.reset_index(drop=True), use_container_width=True)

# ── TAB 4 Top Properties ────────────────────────────────────────────────────
with tab4:
    st.subheader("🏆 Top Properties")
    top_n = st.slider("Show top N", 10, 50, 20)
    top_df = fdf.sort_values("inv_score", ascending=False).head(top_n).reset_index(drop=True)

    def score_color(val):
        if val >= 2.0:   return "background-color:#d1e7dd;color:#0f5132"
        elif val >= 1.5: return "background-color:#fff3cd;color:#856404"
        else:            return "background-color:#f8d7da;color:#842029"

    display_cols = ["address","suburb","council","sale_price","bedrooms","bathrooms",
                    "land_size_sqm","walk_score","school_rating","yield_proxy","inv_score","badges"]
    display_cols = [c for c in display_cols if c in top_df.columns]
    styled = top_df[display_cols].style.map(score_color, subset=["inv_score"]).format({
        "sale_price": "${:,.0f}", "inv_score": "{:.3f}",
        "yield_proxy": "{:.3f}",  "walk_score": "{:.0f}"
    })
    st.dataframe(styled, use_container_width=True, height=500)

    csv_buf = io.BytesIO()
    top_df[display_cols].to_csv(csv_buf, index=False)
    st.download_button("📥 Download Shortlist as CSV", csv_buf, file_name="top_properties.csv")