import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import io
import numpy as np

st.set_page_config(page_title="PropIQ Dashboard", layout="wide", page_icon="🏠")

COUNCIL_MAP = {
    "Fitzroy": "City of Yarra", "Collingwood": "City of Yarra",
    "Richmond": "City of Yarra", "Northcote": "City of Darebin",
    "Brunswick": "City of Moreland", "Footscray": "City of Maribyrnong",
    "Hawthorn": "City of Boroondara", "South Yarra": "City of Stonnington",
    "Prahran": "City of Stonnington", "St Kilda": "City of Port Phillip",
}
SUBURB_COORDS = {
    "Fitzroy": (-37.7988,144.9784), "Collingwood": (-37.8044,144.9880),
    "Richmond": (-37.8182,144.9993), "Northcote": (-37.7714,144.9997),
    "Brunswick": (-37.7664,144.9618), "Footscray": (-37.8008,144.8997),
    "Hawthorn": (-37.8220,145.0334), "South Yarra": (-37.8393,144.9930),
    "Prahran": (-37.8497,144.9929), "St Kilda": (-37.8676,144.9810),
}

st.markdown("""
<style>
  .chat-msg-user { background:#e8f4fd; border-radius:12px 12px 2px 12px;
    padding:10px 14px; margin:6px 0; margin-left:20%; color:#1a1a2e; }
  .chat-msg-bot  { background:#f0f4f0; border-radius:12px 12px 12px 2px;
    padding:10px 14px; margin:6px 0; margin-right:20%; color:#1a1a2e; }
  .chat-label    { font-size:11px; color:#888; margin-bottom:2px; }
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
    df["lat"] = df["suburb"].map(lambda s: SUBURB_COORDS.get(s,(-37.81,144.96))[0])
    df["lng"] = df["suburb"].map(lambda s: SUBURB_COORDS.get(s,(-37.81,144.96))[1])
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
    pmin,pmax = int(df["sale_price"].min()), int(df["sale_price"].max())
    price_range = st.slider("💰 Price Range ($)", pmin, pmax, (pmin,pmax), step=10000)
    bed_options = sorted(df["bedrooms"].dropna().unique().astype(int))
    sel_beds = st.multiselect("🛏️ Bedrooms", bed_options, default=bed_options)
    type_options = sorted(df["house_type"].dropna().unique())
    sel_types = st.multiselect("🏡 Property Type", type_options, default=type_options)
    min_score = st.slider("⭐ Min Inv Score", 0.0, float(df["inv_score"].max()), 0.0, step=0.01)
    st.divider()
    if st.button("🔄 Reset Filters"): st.rerun()

fdf = df[
    df["suburb"].isin(sel_suburbs) &
    df["sale_price"].between(price_range[0], price_range[1]) &
    df["bedrooms"].isin(sel_beds) &
    df["house_type"].isin(sel_types) &
    (df["inv_score"] >= min_score)
]

st.caption(f"Showing **{len(fdf)}** of **{len(df)}** listings")
k1,k2,k3,k4,k5 = st.columns(5)
k1.metric("🏘️ Listings",   len(fdf))
k2.metric("⭐ Avg Score",  f"{fdf['inv_score'].mean():.3f}" if len(fdf) else "—")
k3.metric("💰 Avg Price",  f"${fdf['sale_price'].mean():,.0f}" if len(fdf) else "—")
k4.metric("🏆 Top Suburb", fdf.groupby("suburb")["inv_score"].mean().idxmax() if len(fdf) else "—")
k5.metric("🏛️ Top Council",fdf.groupby("council")["inv_score"].mean().idxmax() if len(fdf) else "—")
st.divider()

tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs([
    "📊 Overview","🗺️ Map","🏛️ Council","🏆 Top Properties","⚖️ Compare","🤖 AI Chat"
])

# TAB 1
with tab1:
    c1,c2 = st.columns(2)
    with c1:
        fig = px.box(fdf,x="suburb",y="inv_score",color="suburb",title="Investment Score by Suburb")
        fig.update_layout(showlegend=False,height=350); st.plotly_chart(fig,use_container_width=True)
    with c2:
        fig = px.scatter(fdf,x="sale_price",y="inv_score",color="suburb",
                         hover_data=["address","badges"],title="Price vs Investment Score")
        fig.update_layout(height=350); st.plotly_chart(fig,use_container_width=True)
    c3,c4 = st.columns(2)
    with c3:
        fig = px.scatter(fdf,x="walk_score",y="inv_score",color="suburb",size="school_rating",
                         hover_data=["address"],title="Walkability vs Score")
        fig.update_layout(height=350); st.plotly_chart(fig,use_container_width=True)
    with c4:
        fig = px.histogram(fdf,x="sale_price",color="suburb",nbins=30,
                           title="Price Distribution",barmode="overlay")
        fig.update_layout(height=350); st.plotly_chart(fig,use_container_width=True)

# TAB 2
with tab2:
    st.subheader("🗺️ Property Map — Melbourne")
    if len(fdf)==0:
        st.warning("No properties match current filters.")
    else:
        map_df = fdf.copy()
        map_df["lat"] += np.random.uniform(-0.003,0.003,len(map_df))
        map_df["lng"] += np.random.uniform(-0.003,0.003,len(map_df))
        fig = px.scatter_mapbox(map_df,lat="lat",lon="lng",color="inv_score",size="inv_score",
            hover_name="address",
            hover_data={"suburb":True,"sale_price":True,"inv_score":True,"council":True,
                        "badges":True,"lat":False,"lng":False},
            color_continuous_scale="RdYlGn",size_max=18,zoom=12,mapbox_style="open-street-map",
            title="Properties coloured & sized by Investment Score")
        fig.update_layout(height=600,margin={"r":0,"t":40,"l":0,"b":0})
        st.plotly_chart(fig,use_container_width=True)

# TAB 3
with tab3:
    st.subheader("🏛️ Council (LGA) Intelligence")
    cs = fdf.groupby("council").agg(listings=("inv_score","count"),avg_score=("inv_score","mean"),
        avg_price=("sale_price","mean"),avg_yield=("yield_proxy","mean"),
        avg_walk=("walk_score","mean"),avg_school=("school_rating","mean")).reset_index().sort_values("avg_score",ascending=False)
    c1,c2 = st.columns(2)
    with c1:
        fig = px.bar(cs,x="council",y="avg_score",color="council",title="Avg Score by Council",text_auto=".3f")
        fig.update_layout(showlegend=False,height=350); st.plotly_chart(fig,use_container_width=True)
    with c2:
        fig = px.bar(cs,x="council",y="avg_price",color="council",title="Avg Price by Council")
        fig.update_layout(showlegend=False,height=350); st.plotly_chart(fig,use_container_width=True)
    metrics=["avg_score","avg_yield","avg_walk","avg_school"]
    labels=["Inv Score","Yield","Walk","School"]
    fig = go.Figure()
    for _,row in cs.iterrows():
        normed=[(row[m]-cs[m].min())/(cs[m].max()-cs[m].min()+1e-9) for m in metrics]+[0]
        normed[-1]=normed[0]
        fig.add_trace(go.Scatterpolar(r=normed,theta=labels+[labels[0]],name=row["council"],fill="toself",opacity=0.5))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,1])),height=450,title="Council Profile Radar")
    st.plotly_chart(fig,use_container_width=True)
    disp=cs.copy(); disp.columns=["Council","Listings","Avg Score","Avg Price","Avg Yield","Avg Walk","Avg School"]
    disp["Avg Price"]=disp["Avg Price"].apply(lambda x:f"${x:,.0f}")
    disp["Avg Score"]=disp["Avg Score"].apply(lambda x:f"{x:.3f}")
    st.dataframe(disp.reset_index(drop=True),use_container_width=True)

# TAB 4
with tab4:
    st.subheader("🏆 Top Properties")
    top_n = st.slider("Show top N",10,50,20)
    top_df = fdf.sort_values("inv_score",ascending=False).head(top_n).reset_index(drop=True)
    def score_color(val):
        if val>=2.0: return "background-color:#d1e7dd;color:#0f5132"
        elif val>=1.5: return "background-color:#fff3cd;color:#856404"
        else: return "background-color:#f8d7da;color:#842029"
    dcols=["address","suburb","council","sale_price","bedrooms","bathrooms",
           "land_size_sqm","walk_score","school_rating","yield_proxy","inv_score","badges"]
    dcols=[c for c in dcols if c in top_df.columns]
    styled=top_df[dcols].style.map(score_color,subset=["inv_score"]).format(
        {"sale_price":"${:,.0f}","inv_score":"{:.3f}","yield_proxy":"{:.3f}","walk_score":"{:.0f}"})
    st.dataframe(styled,use_container_width=True,height=500)
    csv_buf=io.BytesIO(); top_df[dcols].to_csv(csv_buf,index=False)
    st.download_button("📥 Download Shortlist as CSV",csv_buf.getvalue(),"propiq_shortlist.csv","text/csv")
    st.divider()
    st.subheader("🔍 Property Detail")
    sel_addr=st.selectbox("Select a property",top_df["address"].tolist())
    prop=top_df[top_df["address"]==sel_addr].iloc[0]
    c1,c2,c3=st.columns(3)
    c1.metric("💰 Sale Price",f"${prop['sale_price']:,.0f}")
    c2.metric("⭐ Inv Score",f"{prop['inv_score']:.3f}")
    c3.metric("🏛️ Council",prop.get("council","—"))
    c4,c5,c6=st.columns(3)
    c4.metric("🛏️ Bedrooms",int(prop.get("bedrooms",0)))
    c5.metric("🚿 Bathrooms",int(prop.get("bathrooms",0)))
    c6.metric("📐 Land (sqm)",f"{prop.get('land_size_sqm',0):,.0f}")
    c7,c8,c9=st.columns(3)
    c7.metric("🚶 Walk Score",f"{prop.get('walk_score',0):.0f}")
    c8.metric("🏫 School",f"{prop.get('school_rating',0):.1f}")
    c9.metric("📈 Yield",f"{prop.get('yield_proxy',0):.3f}")
    if prop.get("badges"): st.markdown(f"**Badges:** {prop['badges']}")
    rm=[m for m in ["yield_proxy","walk_score","school_rating","ndvi_score","liquidity"] if m in fdf.columns]
    rl=["Yield","Walk","School","NDVI","Liquidity"][:len(rm)]
    if rm:
        normed=[(prop[m]-fdf[m].min())/(fdf[m].max()-fdf[m].min()+1e-9) for m in rm]+[0]
        normed[-1]=normed[0]
        fig=go.Figure(go.Scatterpolar(r=normed,theta=rl+[rl[0]],fill="toself",line_color="#0d6efd"))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,1])),
                          title=f"Investment Profile — {sel_addr}",height=400)
        st.plotly_chart(fig,use_container_width=True)
    if "agent_name" in prop and prop["agent_name"]:
        st.info(f"📞 **{prop['agent_name']}** | {prop.get('agency','')} | [{prop.get('agent_phone','')}](tel:{prop.get('agent_phone','')})")

# TAB 5
with tab5:
    st.subheader("⚖️ Side-by-Side Comparison")
    options=fdf.sort_values("inv_score",ascending=False).head(50)["address"].tolist()
    sel_props=st.multiselect("Select 2–3 properties",options,max_selections=3)
    if len(sel_props)<2:
        st.info("Select at least 2 properties to compare.")
    else:
        comp_df=fdf[fdf["address"].isin(sel_props)].set_index("address")
        ccols=["suburb","council","sale_price","bedrooms","bathrooms","land_size_sqm",
               "house_type","year_built","walk_score","school_rating","yield_proxy",
               "risk_score","ndvi_score","inv_score","badges"]
        ccols=[c for c in ccols if c in comp_df.columns]
        st.dataframe(comp_df[ccols].T,use_container_width=True)
        rm=[m for m in ["yield_proxy","walk_score","school_rating","ndvi_score","liquidity"] if m in fdf.columns]
        rl=["Yield","Walk","School","NDVI","Liquidity"][:len(rm)]
        fig=go.Figure()
        for addr in sel_props:
            row=fdf[fdf["address"]==addr].iloc[0]
            normed=[(row[m]-fdf[m].min())/(fdf[m].max()-fdf[m].min()+1e-9) for m in rm]+[0]
            normed[-1]=normed[0]
            fig.add_trace(go.Scatterpolar(r=normed,theta=rl+[rl[0]],name=addr[:35],fill="toself",opacity=0.6))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,1])),
                          title="Investment Profile Comparison",height=500)
        st.plotly_chart(fig,use_container_width=True)

# TAB 6 — AI CHAT
with tab6:
    st.subheader("🤖 PropIQ AI Assistant")
    st.caption("Ask anything about the property data — powered by LLaMA 3.2 running locally on your machine.")

    # Suggested questions
    st.markdown("**💡 Try asking:**")
    cols = st.columns(3)
    suggestions = [
        "Which suburb has the best yield?",
        "Top 3 properties under $900k?",
        "Which council is safest to invest in?",
        "Best walkable suburbs for families?",
        "Compare Brunswick vs Fitzroy",
        "Highest scoring 3-bed houses?",
    ]
    for i, sug in enumerate(suggestions):
        if cols[i % 3].button(sug, key=f"sug_{i}"):
            st.session_state.setdefault("chat_history", [])
            st.session_state["pending_question"] = sug

    st.divider()

    # Chat history display
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for turn in st.session_state["chat_history"]:
        st.markdown(f'<div class="chat-label">You</div><div class="chat-msg-user">{turn["user"]}</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="chat-label">PropIQ AI</div><div class="chat-msg-bot">{turn["assistant"]}</div>',
                    unsafe_allow_html=True)

    # Input
    with st.form("chat_form", clear_on_submit=True):
        default_q = st.session_state.pop("pending_question", "")
        user_input = st.text_input("Ask PropIQ AI...", value=default_q,
                                   placeholder="e.g. Which suburb has the best risk-adjusted returns?")
        submitted = st.form_submit_button("Send 🚀")

    if submitted and user_input.strip():
        with st.spinner("PropIQ AI is thinking..."):
            try:
                from propiq_chat import ask, load_latest_report
                chat_df = load_latest_report()
                answer = ask(user_input, chat_df, st.session_state["chat_history"])
            except ImportError:
                answer = "❌ propiq_chat.py not found. Make sure it's in the project root."
            except Exception as e:
                answer = f"❌ Error: {e}"

        st.session_state["chat_history"].append({
            "user": user_input,
            "assistant": answer
        })
        st.rerun()

    if st.session_state["chat_history"]:
        if st.button("🗑️ Clear chat"):
            st.session_state["chat_history"] = []
            st.rerun()
