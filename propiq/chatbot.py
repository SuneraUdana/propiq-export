"""PropIQ — Conversational Chatbot Engine (intent → SQL → response)"""
import re, json, sqlite3
from datetime import datetime
from propiq.config import DB_PATH

INTENTS = {
    "top_properties":  r"\b(top|best|highest.?score|recommend|shortlist|investment)\b",
    "suburb_analysis": r"\b(suburb|area|neighbourhood|about|tell me about)\b",
    "suburb_compare":  r"\b(compare|versus|vs|between|better)\b",
    "material_query":  r"\b(brick|weatherboard|timber|material)\b",
    "tree_query":      r"\b(tree|canopy|vegetation|palm|giant tree)\b",
    "price_query":     r"\b(price|cost|cheap|afford|budget|under|\$|million)\b",
    "agent_query":     r"\b(agent|agency|broker|contact)\b",
    "year_query":      r"\b(year|built|age|old|heritage|historic|edwardian|victorian)\b",
    "land_query":      r"\b(land|size|sqm|block|large|biggest)\b",
    "score_explain":   r"\b(score|rank|explain|how|why|weight|factor)\b",
    "stats_overview":  r"\b(summary|overview|stat|total|count|dataset|all)\b",
    "help":            r"\b(hi|hello|hey|help|what can|example)\b",
}

def _intent(text):
    t = text.lower()
    for k, pat in INTENTS.items():
        if re.search(pat, t): return k
    return "top_properties"

def _suburb(text):
    subs = ["fitzroy","richmond","hawthorn","brunswick","south yarra",
            "collingwood","st kilda","prahran","northcote","footscray"]
    t = text.lower()
    for s in subs:
        if s in t: return s.title()
    return None

def _price_cap(text):
    m = re.search(r"\$?([\d,]+\.?\d*)\s*(m|million|k)?", text.lower())
    if not m: return None
    v = float(m.group(1).replace(",",""))
    u = (m.group(2) or "").lower()
    if u.startswith("m"): v *= 1e6
    if u == "k": v *= 1e3
    return v

def _conn():
    c = sqlite3.connect(DB_PATH); c.row_factory = sqlite3.Row; return c

def _fmt(v):
    try: return f"${float(v):,.0f}"
    except: return "—"

def _score_icon(s):
    return "🟢" if s>=0.90 else ("🟡" if s>=0.70 else "🔴")

def respond(user_input):
    kind = _intent(user_input)
    sub  = _suburb(user_input)
    cap  = _price_cap(user_input)
    c    = _conn()

    if kind == "help":
        return ("**PropIQ Chat** 🏠\n\nI can answer questions about Melbourne sold properties.\n\n"
                "Try: top properties · suburb analysis · brick houses · tree flags · "
                "price filters · agent performance · heritage properties · explain scoring")

    if kind == "stats_overview":
        r = c.execute("SELECT COUNT(*) as n FROM listings").fetchone()
        subs = c.execute("SELECT COUNT(DISTINCT suburb) as n FROM listings").fetchone()
        brick = c.execute("SELECT COUNT(*) as n FROM enrichments WHERE material='brick'").fetchone()
        tree  = c.execute("SELECT COUNT(*) as n FROM enrichments WHERE tree_flag=1").fetchone()
        ts    = c.execute("SELECT suburb, AVG(s.inv_score) as sc FROM listings l "
                          "JOIN scores s ON l.listing_id=s.listing_id "
                          "GROUP BY suburb ORDER BY sc DESC LIMIT 1").fetchone()
        return (f"**Dataset Overview** 📊\n\n🏡 {r['n']} properties · 📍 {subs['n']} suburbs\n"
                f"🧱 {brick['n']} brick · 🌳 {tree['n']} tree flags\n"
                f"🏆 Top suburb: **{ts['suburb']}** (score {ts['sc']:.4f})")

    if kind == "score_explain":
        w_row = c.execute("SELECT weights_json FROM scores LIMIT 1").fetchone()
        try: w = json.loads(w_row["weights_json"]); t = sum(w); pct=[round(v/t*100,1) for v in w]
        except: pct=[32.8,1.6,32.8,32.8]
        return (f"**Scoring Formula** 🤖\n\n`score = w₀×yield − w₁×risk + w₂×liquidity + w₃×quality`\n\n"
                f"w₀ Yield proxy: **{pct[0]}%**\n"
                f"w₁ Risk penalty: **{pct[1]}%**\n"
                f"w₂ Liquidity (walk score): **{pct[2]}%**\n"
                f"w₃ Quality (school, brick, NLP): **{pct[3]}%**\n\n"
                "Weights tuned via Differential Evolution on historical data.")

    if kind == "suburb_compare":
        subs = ["fitzroy","richmond","hawthorn","brunswick","south yarra",
                "collingwood","st kilda","prahran","northcote","footscray"]
        found = [s.title() for s in subs if s in user_input.lower()][:2]
        if len(found) < 2: kind = "suburb_analysis"
        else:
            lines = [f"**{' vs '.join(found)}** ⚖️\n"]
            for fs in found:
                r = c.execute("""SELECT AVG(l.sale_price) as ap, AVG(s.inv_score) as sc,
                                        e.walk_score, e.school_rating
                                 FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id
                                 JOIN scores s ON l.listing_id=s.listing_id
                                 WHERE l.suburb=? LIMIT 1""", [fs]).fetchone()
                if r:
                    lines.append(f"**{fs}** — Score: {r['sc']:.4f} · Avg: {_fmt(r['ap'])} · "
                                 f"Walk: {r['walk_score']}/100 · School: {r['school_rating']:.1f}/10")
            return "\n".join(lines)

    if kind == "suburb_analysis":
        if sub:
            r = c.execute("""SELECT COUNT(*) as cnt, AVG(l.sale_price) as ap,
                                    MIN(l.sale_price) as mn, MAX(l.sale_price) as mx,
                                    AVG(s.inv_score) as sc, e.walk_score, e.school_rating,
                                    SUM(CASE WHEN e.material='brick' THEN 1 ELSE 0 END) as bk,
                                    SUM(e.tree_flag) as tr, e.suburb_income
                             FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id
                             JOIN scores s ON l.listing_id=s.listing_id
                             WHERE l.suburb=?""", [sub]).fetchone()
            if not r or not r["cnt"]: return f"No data for **{sub}**."
            bp = round(r["bk"]/r["cnt"]*100)
            tp = round(r["tr"]/r["cnt"]*100)
            return (f"**{sub} Report** 📊\n\n📦 {r['cnt']} properties\n"
                    f"💰 {_fmt(r['mn'])} – {_fmt(r['mx'])} · Avg {_fmt(r['ap'])}\n"
                    f"🧱 Brick {bp}% · 🌳 Tree risk {tp}%\n"
                    f"🚶 Walk {r['walk_score']}/100 · 🏫 School {r['school_rating']:.1f}/10\n"
                    f"💼 Median income: {_fmt(r['suburb_income'])}\n"
                    f"{_score_icon(r['sc'])} Avg score: **{r['sc']:.4f}**")
        rows = c.execute("""SELECT l.suburb, COUNT(*) as cnt, AVG(s.inv_score) as sc,
                                   AVG(l.sale_price) as ap
                            FROM listings l JOIN scores s ON l.listing_id=s.listing_id
                            GROUP BY l.suburb ORDER BY sc DESC""").fetchall()
        return "**Suburb Rankings** 🏆\n\n" + "\n".join(
            f"{i}. **{r['suburb']}** — {r['sc']:.4f} · {_fmt(r['ap'])} · {r['cnt']} listings"
            for i,r in enumerate(rows,1))

    if kind == "material_query":
        mat = "weatherboard" if any(w in user_input.lower() for w in ["weatherboard","timber","wb"]) else "brick"
        q = ("SELECT l.suburb, l.address, l.sale_price, s.inv_score FROM listings l "
             "JOIN enrichments e ON l.listing_id=e.listing_id "
             "JOIN scores s ON l.listing_id=s.listing_id WHERE e.material=?")
        params = [mat]
        if sub: q += " AND l.suburb=?"; params.append(sub)
        q += " ORDER BY s.inv_score DESC LIMIT 5"
        rows = c.execute(q, params).fetchall()
        scope = f" in {sub}" if sub else ""
        return (f"**Top {mat.title()} Properties{scope}** 🧱\n\n" +
                "\n".join(f"#{i} {r['suburb']} · {_fmt(r['sale_price'])} · Score: {r['inv_score']:.4f}"
                          for i,r in enumerate(rows,1)))

    if kind == "tree_query":
        flag = 0 if any(w in user_input.lower() for w in ["no tree","without","clear"]) else 1
        label = "WITH" if flag else "WITHOUT"
        rows = c.execute("""SELECT l.suburb, l.address, l.sale_price, e.ndvi_score, s.inv_score
                            FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id
                            JOIN scores s ON l.listing_id=s.listing_id
                            WHERE e.tree_flag=? ORDER BY s.inv_score DESC LIMIT 5""", [flag]).fetchall()
        n = c.execute("SELECT COUNT(*) as n FROM enrichments WHERE tree_flag=1").fetchone()["n"]
        return (f"**Properties {label} Tree Flag** 🌳  ({n}/100 flagged)\n\n" +
                "\n".join(f"#{i} {r['suburb']} · {_fmt(r['sale_price'])} · NDVI {r['ndvi_score']:.3f} · Score {r['inv_score']:.4f}"
                          for i,r in enumerate(rows,1)))

    if kind == "price_query":
        cheap = any(w in user_input.lower() for w in ["cheap","budget","lowest","under","afford"])
        q = ("SELECT l.suburb, l.address, l.sale_price, e.material, s.inv_score "
             "FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id "
             "JOIN scores s ON l.listing_id=s.listing_id WHERE 1=1")
        params = []
        if cap: q += " AND l.sale_price<=?"; params.append(cap)
        if sub: q += " AND l.suburb=?"; params.append(sub)
        q += f" ORDER BY l.sale_price {'ASC' if cheap else 'DESC'} LIMIT 5"
        rows = c.execute(q, params).fetchall()
        cap_s = f" under {_fmt(cap)}" if cap else ""
        return (f"**Properties{cap_s}** 💰\n\n" +
                "\n".join(f"#{i} {r['suburb']} · {_fmt(r['sale_price'])} · {r['material']} · Score {r['inv_score']:.4f}"
                          for i,r in enumerate(rows,1)))

    if kind == "agent_query":
        q = ("SELECT l.agent_name, l.agency, COUNT(*) as cnt, AVG(s.inv_score) as sc "
             "FROM listings l JOIN scores s ON l.listing_id=s.listing_id ")
        params = []
        if sub: q += "WHERE l.suburb=? "; params.append(sub)
        q += "GROUP BY l.agent_name ORDER BY sc DESC LIMIT 6"
        rows = c.execute(q, params).fetchall()
        scope = f" in {sub}" if sub else ""
        return (f"**Top Agents{scope}** 👤\n\n" +
                "\n".join(f"#{i} **{r['agent_name']}** ({r['agency']}) · {r['cnt']} listings · Score {r['sc']:.4f}"
                          for i,r in enumerate(rows,1)))

    if kind == "year_query":
        old = any(w in user_input.lower() for w in ["old","heritage","oldest","period","historic","edwardian","victorian"])
        q = ("SELECT l.suburb, l.address, l.year_built, l.sale_price, e.material, s.inv_score "
             "FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id "
             f"JOIN scores s ON l.listing_id=s.listing_id ORDER BY l.year_built {'ASC' if old else 'DESC'} LIMIT 5")
        rows = c.execute(q).fetchall()
        return (f"**{'Heritage / Oldest' if old else 'Newest'} Properties** 🏛\n\n" +
                "\n".join(f"#{i} {r['suburb']} · Built {r['year_built']} · {_fmt(r['sale_price'])} · {r['material']}"
                          for i,r in enumerate(rows,1)))

    if kind == "land_query":
        large = any(w in user_input.lower() for w in ["large","big","biggest","most","spacious"])
        rows = c.execute(f"""SELECT l.suburb, l.address, l.land_size_sqm, l.sale_price, s.inv_score
                             FROM listings l JOIN scores s ON l.listing_id=s.listing_id
                             WHERE l.land_size_sqm>0 ORDER BY l.land_size_sqm {'DESC' if large else 'ASC'}
                             LIMIT 5""").fetchall()
        return (f"**{'Largest' if large else 'Smallest'} Blocks** 📐\n\n" +
                "\n".join(f"#{i} {r['suburb']} · {int(r['land_size_sqm']):,} m² · {_fmt(r['sale_price'])} · Score {r['inv_score']:.4f}"
                          for i,r in enumerate(rows,1)))

    # default: top properties
    q = ("SELECT l.suburb, l.address, l.sale_price, l.house_type, e.material, e.tree_flag, s.inv_score "
         "FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id "
         "JOIN scores s ON l.listing_id=s.listing_id")
    params = []
    if sub: q += " WHERE l.suburb=?"; params.append(sub)
    q += " ORDER BY s.inv_score DESC LIMIT 5"
    rows = c.execute(q, params).fetchall()
    scope = f" in {sub}" if sub else ""
    return (f"**Top Investment Picks{scope}** 🏡\n\n" +
            "\n".join(
                f"#{i} **{r['suburb']}** · {_fmt(r['sale_price'])} · "
                f"{r['material']} · {'🌳' if r['tree_flag'] else '—'} · "
                f"{_score_icon(r['inv_score'])} {r['inv_score']:.4f}"
                for i,r in enumerate(rows,1)))

