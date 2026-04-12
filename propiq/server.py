import sqlite3, json
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from propiq.config import DB_PATH, TARGET_SUBURBS
from propiq.storage import init_db

BASE = Path(__file__).parent.parent
OUT  = BASE / "output" / "propiq-chatbot.html"
BASE.joinpath("output").mkdir(exist_ok=True)

init_db()

def _has_data():
    try:
        return sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM scores").fetchone()[0] >= 10
    except:
        return False

if not _has_data():
    print("[server] No data — running pipeline...")
    from propiq.agent import run_pipeline
    run_pipeline(TARGET_SUBURBS[:5])

def build_ui():
    print("[server] Building UI...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    props = conn.execute("""SELECT l.suburb,l.address,l.sale_price,l.land_size_sqm,
        l.house_type,l.year_built,l.agent_name,l.agency,
        e.material,e.tree_flag,e.walk_score,e.school_rating,s.inv_score
        FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id
        JOIN scores s ON l.listing_id=s.listing_id
        ORDER BY s.inv_score DESC""").fetchall()
    subs = conn.execute("""SELECT l.suburb,COUNT(*) AS cnt,AVG(l.sale_price) AS ap,
        AVG(s.inv_score) AS sc,
        SUM(CASE WHEN e.material='brick' THEN 1 ELSE 0 END)*100/COUNT(*) AS bp,
        SUM(e.tree_flag)*100/COUNT(*) AS tp,
        AVG(e.walk_score) AS ws,AVG(e.school_rating) AS sr
        FROM listings l JOIN enrichments e ON l.listing_id=e.listing_id
        JOIN scores s ON l.listing_id=s.listing_id
        GROUP BY l.suburb ORDER BY sc DESC""").fetchall()
    ags = conn.execute("""SELECT l.agent_name,l.agency,COUNT(*) AS cnt,AVG(s.inv_score) AS sc
        FROM listings l JOIN scores s ON l.listing_id=s.listing_id
        GROUP BY l.agent_name ORDER BY sc DESC LIMIT 8""").fetchall()
    wr = conn.execute("SELECT weights_json FROM scores WHERE weights_json IS NOT NULL LIMIT 1").fetchone()
    try:
        w = json.loads(wr["weights_json"]); t = sum(w) or 1
        wp = [round(v/t*100,1) for v in w]
    except:
        wp = [33.0,1.0,33.0,33.0]
    conn.close()
    D = json.dumps({
        "props":   [dict(r) for r in props],
        "suburbs": [dict(r) for r in subs],
        "agents":  [dict(r) for r in ags],
        "w_pct":   wp,
        "total":   len(props),
    })
    html = _make_html(D)
    OUT.write_text(html, encoding="utf-8")
    print(f"[server] UI ready -> {OUT}")

def _make_html(D):
    return """<!DOCTYPE html><html lang="en" data-theme="dark"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PropIQ Chat</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300..700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root,[data-theme=light]{--bg:#f7f6f2;--surf:#f0ede8;--s2:#e8e5e0;--br:#d4d1ca;--tx:#28251d;--mu:#7a7974;--fa:#bab9b4;--p:#01696f;--ph:#0c4e54;--pl:#cedcd8;--bt:#e8f3f2;--us:#01696f;--gn:#437a22;--or:#da7101}
[data-theme=dark]{--bg:#111110;--surf:#1c1b19;--s2:#242321;--br:#333230;--tx:#d4d3d0;--mu:#797876;--fa:#4a4947;--p:#4f98a3;--ph:#227f8b;--pl:#1e3436;--bt:#1a2b2e;--us:#1e3436;--gn:#6daa45;--or:#fdab43}
*{box-sizing:border-box;margin:0;padding:0}html,body{height:100%;font-family:Inter,system-ui,sans-serif;font-size:14px;background:var(--bg);color:var(--tx);-webkit-font-smoothing:antialiased}
button{cursor:pointer;background:none;border:none;font:inherit;color:inherit}
.app{display:grid;grid-template-columns:270px 1fr;height:100dvh;overflow:hidden}
@media(max-width:700px){.app{grid-template-columns:1fr}.sb{display:none}}
.sb{display:flex;flex-direction:column;background:var(--surf);border-right:1px solid var(--br);overflow:hidden}
.sbh{padding:.875rem 1rem;border-bottom:1px solid var(--br);display:flex;align-items:center;justify-content:space-between}
.logo{font-weight:700;font-size:.9rem;letter-spacing:-.02em}.logo span{color:var(--p)}
.tb{padding:.28rem .45rem;border-radius:.4rem;border:1px solid var(--br);font-size:.75rem;color:var(--mu)}.tb:hover{background:var(--s2)}
.sc2{flex:1;overflow-y:auto;padding:.75rem}
.lb{font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--fa);margin:.75rem 0 .3rem}.lb:first-child{margin-top:0}
.kg{display:grid;grid-template-columns:1fr 1fr;gap:.35rem;margin-bottom:.5rem}
.kc{background:var(--bg);border:1px solid var(--br);border-radius:.5rem;padding:.45rem .6rem}
.kv{font-size:1.05rem;font-weight:700;color:var(--p)}.kl{font-size:.58rem;color:var(--mu)}
.sr{display:flex;align-items:center;justify-content:space-between;padding:.3rem .45rem;border-radius:.4rem;cursor:pointer;border:1px solid transparent}.sr:hover{background:var(--s2);border-color:var(--br)}
.sn{font-size:.75rem;font-weight:600}
.ss{font-family:JetBrains Mono,monospace;font-size:.65rem;font-weight:700;padding:.08rem .35rem;border-radius:9999px;color:#fff}
.qc{display:inline-flex;padding:.22rem .5rem;border-radius:9999px;border:1px solid var(--br);background:var(--bg);font-size:.67rem;color:var(--mu);cursor:pointer;margin:.1rem}.qc:hover{border-color:var(--p);color:var(--p);background:var(--pl)}
.ch{display:flex;flex-direction:column;height:100dvh;overflow:hidden}
.chh{padding:.75rem 1.125rem;background:var(--bg);border-bottom:1px solid var(--br);display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.ct{font-weight:700;font-size:.9rem}.cs{font-size:.67rem;color:var(--mu)}
.bd{display:flex;align-items:center;gap:.3rem;font-size:.67rem;color:var(--mu);background:var(--surf);border:1px solid var(--br);padding:.15rem .45rem;border-radius:9999px}
.dt{width:6px;height:6px;border-radius:50%;background:var(--gn);animation:pu 2s infinite}
@keyframes pu{0%,100%{opacity:1}50%{opacity:.35}}
.ms{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.75rem}.ms::-webkit-scrollbar{width:3px}.ms::-webkit-scrollbar-thumb{background:var(--br)}
.mg{display:flex;align-items:flex-end;gap:.45rem;max-width:90%}.mg.b{align-self:flex-start}.mg.u{align-self:flex-end;flex-direction:row-reverse}
.av{width:26px;height:26px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700}
.av.b{background:var(--pl);color:var(--p)}.av.u{background:var(--p);color:#fff}
.bb{padding:.575rem .8rem;border-radius:.8rem;line-height:1.65;font-size:.8rem}
.bb.b{background:var(--bt);border:1px solid var(--br);border-bottom-left-radius:.2rem}
.bb.u{background:var(--us);border:1px solid color-mix(in oklch,var(--p) 40%,var(--br));border-bottom-right-radius:.2rem}
.bb b,.bb strong{color:var(--p)}.bb code{font-family:JetBrains Mono,monospace;font-size:.75em;background:var(--s2);padding:.1em .3em;border-radius:.2rem;color:var(--or)}
.ts{font-size:.6rem;color:var(--fa);margin-top:.15rem}
.ty span{width:6px;height:6px;border-radius:50%;background:var(--mu);display:inline-block;animation:bl 1.4s infinite;margin:.1rem}.ty span:nth-child(2){animation-delay:.2s}.ty span:nth-child(3){animation-delay:.4s}
@keyframes bl{0%,60%,100%{opacity:.25}30%{opacity:1}}
.sg{display:flex;gap:.3rem;overflow-x:auto;padding:.5rem 1rem;border-top:1px solid var(--br);flex-shrink:0}.sg::-webkit-scrollbar{display:none}
.sc{white-space:nowrap;padding:.22rem .55rem;border-radius:9999px;border:1px solid var(--br);background:var(--surf);font-size:.67rem;color:var(--mu);cursor:pointer;flex-shrink:0}.sc:hover{border-color:var(--p);color:var(--p);background:var(--pl)}
.ir{display:flex;align-items:flex-end;gap:.5rem;padding:.75rem 1rem .875rem;background:var(--bg);border-top:1px solid var(--br);flex-shrink:0}
#inp{flex:1;padding:.55rem .8rem;border-radius:.575rem;border:1px solid var(--br);background:var(--surf);color:var(--tx);font:inherit;font-size:.82rem;outline:none;resize:none;min-height:36px;max-height:100px;line-height:1.5}
#inp:focus{border-color:var(--p)}#inp::placeholder{color:var(--fa)}
.sbt{width:36px;height:36px;border-radius:.575rem;background:var(--p);color:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0}.sbt:hover{background:var(--ph)}.sbt:disabled{background:var(--br);color:var(--fa)}
.pc{background:var(--surf);border:1px solid var(--br);border-radius:.625rem;padding:.625rem;margin:.25rem 0;font-size:.75rem}
.pt{display:flex;justify-content:space-between;align-items:center;margin-bottom:.25rem}
.rk{font-family:JetBrains Mono,monospace;font-weight:700;color:var(--p);font-size:.65rem}
.ps{padding:.1rem .375rem;border-radius:9999px;font-family:JetBrains Mono,monospace;font-size:.65rem;font-weight:700;color:#fff}
.pu2{font-weight:700}.pa{font-size:.67rem;color:var(--mu);margin:.08rem 0 .25rem}
.tg{display:flex;flex-wrap:wrap;gap:.18rem;margin-top:.25rem}
.tg span{padding:.06rem .32rem;border-radius:9999px;font-size:.63rem;border:1px solid var(--br);background:var(--s2);color:var(--mu)}
.tg .g{border-color:var(--gn);color:var(--gn)}.tg .o{border-color:var(--or);color:var(--or)}.tg .bl{border-color:#5591c7;color:#5591c7}
.tb2{width:100%;border-collapse:collapse;font-size:.73rem;margin:.35rem 0}
.tb2 th{background:var(--s2);padding:.3rem .5rem;text-align:left;font-size:.62rem;text-transform:uppercase;letter-spacing:.06em;color:var(--mu);border-bottom:1px solid var(--br)}
.tb2 td{padding:.3rem .5rem;border-bottom:1px solid color-mix(in oklch,var(--br) 45%,transparent)}
.tb2 tr:last-child td{border-bottom:none}.tb2 tr:hover td{background:var(--s2)}
</style></head><body>
<div class="app">
<aside class="sb">
  <div class="sbh"><div class="logo">Prop<span>IQ</span></div><button class="tb" id="ttog">🌙</button></div>
  <div class="sc2">
    <div class="lb">Dataset</div><div class="kg" id="kg"></div>
    <div class="lb">Suburbs</div><div id="sl"></div>
    <div class="lb">Quick Asks</div><div id="ql"></div>
  </div>
</aside>
<div class="ch">
  <div class="chh">
    <div><div class="ct">PropIQ Advisor</div><div class="cs">Melbourne sold property intelligence</div></div>
    <div class="bd"><div class="dt"></div>Live</div>
  </div>
  <div class="ms" id="ms"></div>
  <div class="sg" id="sg"></div>
  <div class="ir">
    <textarea id="inp" rows="1" placeholder="Ask about suburbs, prices, materials, agents…"></textarea>
    <button class="sbt" id="sbt"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
  </div>
</div>
</div>
<script>
const D=""" + D + """;
const root=document.documentElement;let th='dark';
document.getElementById('ttog').addEventListener('click',()=>{th=th==='dark'?'light':'dark';root.setAttribute('data-theme',th);document.getElementById('ttog').textContent=th==='dark'?'🌙':'☀️'});
const sc=s=>s>=.9?'#6daa45':s>=.7?'#fdab43':'#dd6974';
const si=s=>s>=.9?'🟢':s>=.7?'🟡':'🔴';
const fp=v=>v?'$'+Math.round(v).toLocaleString():'—';
const br=D.props.filter(p=>p.material==='brick').length;
const tr=D.props.filter(p=>p.tree_flag).length;
document.getElementById('kg').innerHTML=[{v:D.total,l:'Properties'},{v:D.suburbs.length,l:'Suburbs'},{v:br,l:'Brick'},{v:tr,l:'Tree Flags'}].map(k=>`<div class="kc"><div class="kv">${k.v}</div><div class="kl">${k.l}</div></div>`).join('');
document.getElementById('sl').innerHTML=D.suburbs.map(s=>`<div class="sr" onclick="snd('Tell me about ${s.suburb}')"><span class="sn">${s.suburb}</span><span class="ss" style="background:${sc(s.sc)}">${s.sc.toFixed(3)}</span></div>`).join('');
['Top 5 picks','Best suburb?','Brick houses','Tree properties','Under $900K','Best agent?','Overview','Scoring logic'].forEach(q=>{const e=document.createElement('span');e.className='qc';e.textContent='💬 '+q;e.onclick=()=>snd(q);document.getElementById('ql').appendChild(e)});
['🏆 Top picks','📊 Suburbs','🧱 Brick','🌳 Trees','💰 Price','👤 Agents','🤖 Score'].forEach(q=>{const e=document.createElement('span');e.className='sc';e.textContent=q;e.onclick=()=>snd(q);document.getElementById('sg').appendChild(e)});
function intent(t){const l=t.toLowerCase();
  if(/\b(top|best invest|recommend|pick|shortlist)\b/.test(l))return'top';
  if(/\b(compare|vs|versus|between)\b/.test(l))return'compare';
  if(/\b(brick|weatherboard|timber|wb|material)\b/.test(l))return'mat';
  if(/\b(tree|canopy|vegetation)\b/.test(l))return'tree';
  if(/\b(price|cost|cheap|afford|under|\$|budget|900)\b/.test(l))return'price';
  if(/\b(agent|agency|broker)\b/.test(l))return'agent';
  if(/\b(year|built|age|old|heritage|edwardian)\b/.test(l))return'year';
  if(/\b(land|sqm|block|size|large|biggest)\b/.test(l))return'land';
  if(/\b(score|how|why|weight|logic|explain|factor)\b/.test(l))return'explain';
  if(/\b(suburb|area|about|tell|ranking|neighbourhood)\b/.test(l))return'sub';
  if(/\b(overview|summary|stat|total|count|all|dataset)\b/.test(l))return'overview';
  return'top'}
function gsub(t){return['fitzroy','richmond','hawthorn','brunswick','south yarra','collingwood','st kilda','prahran','northcote','footscray'].find(s=>t.toLowerCase().includes(s))||null}
function gcap(t){const m=t.match(/\$?([\d,]+)\.?\d*\s*(m|million|k)?/i);if(!m)return null;let v=parseFloat(m[1].replace(/,/g,''));const u=(m[2]||'').toLowerCase();if(u.startsWith('m'))v*=1e6;if(u==='k')v*=1e3;return v}
function pc(p,i){const s=p.inv_score;return`<div class="pc"><div class="pt"><span class="rk">#${i}</span><span class="ps" style="background:${sc(s)}">${s.toFixed(4)}</span></div><div class="pu2">${p.suburb}</div><div class="pa">📍 ${p.address}</div><div style="font-weight:700">${fp(p.sale_price)}</div><div class="tg"><span class="${p.material==='brick'?'g':'bl'}">${p.material==='brick'?'🧱 Brick':'🪵 WB'}</span>${p.tree_flag?'<span class="o">🌳 Tree</span>':''}<span>🏠 ${p.house_type}</span><span>📐 ${Math.round(p.land_size_sqm).toLocaleString()}m²</span><span>👤 ${p.agent_name}</span></div></div>`}
function resp(t){
  const k=intent(t),sub=gsub(t),cap=gcap(t);
  if(k==='overview'){const ts=D.suburbs[0],ta=D.agents[0];return`<b>Overview</b> 📊<br>🏡 <b>${D.total}</b> props · 📍 <b>${D.suburbs.length}</b> suburbs<br>🧱 <b>${br}</b> brick · 🌳 <b>${tr}</b> tree flags<br>🏆 <b>${ts.suburb}</b> (${ts.sc.toFixed(4)})<br>👤 <b>${ta.agent_name}</b>`}
  if(k==='explain'){const w=D.w_pct;return`<b>Score Formula</b> 🤖<br><code>score = w₀×yield − w₁×risk + w₂×walk + w₃×quality</code><br><table class="tb2"><thead><tr><th>Weight</th><th>Factor</th><th>%</th></tr></thead><tbody><tr><td>w₀</td><td>Yield</td><td><b>${w[0]}%</b></td></tr><tr><td>w₁</td><td>Risk</td><td><b>${w[1]}%</b></td></tr><tr><td>w₂</td><td>Liquidity</td><td><b>${w[2]}%</b></td></tr><tr><td>w₃</td><td>Quality</td><td><b>${w[3]}%</b></td></tr></tbody></table>`}
  if(k==='compare'){const ss=['fitzroy','richmond','hawthorn','brunswick','south yarra','collingwood','st kilda','prahran','northcote','footscray'];const f=ss.filter(s=>t.toLowerCase().includes(s)).slice(0,2);if(f.length<2)return resp('suburb rankings');const rows=f.map(s=>{const d=D.suburbs.find(x=>x.suburb.toLowerCase()===s);return d?`<tr><td><b>${d.suburb}</b></td><td>${fp(d.ap)}</td><td style="color:${sc(d.sc)};font-weight:700">${d.sc.toFixed(4)}</td><td>${d.bp}%</td></tr>`:''}).join('');return`<b>Comparison</b> ⚖️<br><table class="tb2"><thead><tr><th>Suburb</th><th>Avg</th><th>Score</th><th>Brick%</th></tr></thead><tbody>${rows}</tbody></table>`}
  if(k==='sub'){if(sub){const d=D.suburbs.find(x=>x.suburb.toLowerCase()===sub);if(!d)return`No data for <b>${sub}</b>`;return`<b>${d.suburb}</b> 📊<br>📦 ${d.cnt} properties · Avg ${fp(d.ap)}<br>🧱 Brick ${d.bp}% · 🌳 Trees ${d.tp}%<br>🚶 Walk ${Math.round(d.ws)}/100 · 🏫 School ${d.sr.toFixed(1)}/10<br>${si(d.sc)} Score <b>${d.sc.toFixed(4)}</b>`}const rows=D.suburbs.map((d,i)=>`<tr><td><b>${i+1}. ${d.suburb}</b></td><td>${fp(d.ap)}</td><td style="color:${sc(d.sc)};font-weight:700">${d.sc.toFixed(4)}</td><td>${d.bp}%</td></tr>`).join('');return`<b>Suburb Rankings</b> 🏆<br><table class="tb2"><thead><tr><th>Suburb</th><th>Avg Price</th><th>Score</th><th>Brick%</th></tr></thead><tbody>${rows}</tbody></table>`}
  if(k==='mat'){const mat=/weatherboard|timber|wb/.test(t.toLowerCase())?'weatherboard':'brick';let p=D.props.filter(x=>x.material===mat);if(sub)p=p.filter(x=>x.suburb.toLowerCase()===sub);return`<b>Top ${mat}</b> 🧱<br>`+p.slice(0,5).map((x,i)=>pc(x,i+1)).join('')}
  if(k==='tree'){const want=!/no.?tree|without/.test(t.toLowerCase());return`<b>${want?'With':'Without'} Tree Flag</b> 🌳<br>`+D.props.filter(x=>!!x.tree_flag===want).slice(0,5).map((x,i)=>pc(x,i+1)).join('')}
  if(k==='price'){let p=D.props.slice();if(cap)p=p.filter(x=>x.sale_price<=cap);if(sub)p=p.filter(x=>x.suburb.toLowerCase()===sub);if(/cheap|under|lowest/.test(t.toLowerCase()))p.sort((a,b)=>a.sale_price-b.sale_price);return`<b>Properties${cap?' under '+fp(cap):''}</b> 💰<br>`+p.slice(0,5).map((x,i)=>pc(x,i+1)).join('')}
  if(k==='agent'){const rows=D.agents.map((a,i)=>`<tr><td><b>#${i+1} ${a.agent_name}</b><br><span style="color:var(--mu);font-size:.67rem">${a.agency}</span></td><td>${a.cnt}</td><td><span class="ps" style="background:${sc(a.sc)}">${a.sc.toFixed(4)}</span></td></tr>`).join('');return`<b>Top Agents</b> 👤<br><table class="tb2"><thead><tr><th>Agent</th><th>#</th><th>Score</th></tr></thead><tbody>${rows}</tbody></table>`}
  if(k==='year'){const old=/old|heritage|edwardian|victorian/.test(t.toLowerCase());return`<b>${old?'Heritage':'Newest'}</b> 🏛<br>`+D.props.slice().sort((a,b)=>old?a.year_built-b.year_built:b.year_built-a.year_built).slice(0,5).map((x,i)=>pc(x,i+1)).join('')}
  if(k==='land'){const lg=/large|big|biggest/.test(t.toLowerCase());return`<b>${lg?'Largest':'Smallest'} Blocks</b> 📐<br>`+D.props.slice().sort((a,b)=>lg?b.land_size_sqm-a.land_size_sqm:a.land_size_sqm-b.land_size_sqm).slice(0,5).map((x,i)=>pc(x,i+1)).join('')}
  let p=D.props.slice();if(sub)p=p.filter(x=>x.suburb.toLowerCase()===sub);
  return`<b>Top Picks${sub?' in '+sub.charAt(0).toUpperCase()+sub.slice(1):''}</b> 🏡<br>`+p.slice(0,5).map((x,i)=>pc(x,i+1)).join('')}
const msEl=document.getElementById('ms'),inEl=document.getElementById('inp'),sb=document.getElementById('sbt');
function now(){return new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function add(html,r){const d=document.createElement('div');d.className='mg '+r;d.innerHTML=`<div class="av ${r}">${r==='b'?'🏠':'U'}</div><div><div class="bb ${r}">${html}</div><div class="ts">${now()}</div></div>`;msEl.appendChild(d);msEl.scrollTop=msEl.scrollHeight}
function styp(){const d=document.createElement('div');d.id='tp';d.className='mg b';d.innerHTML='<div class="av b">🏠</div><div class="bb b"><div class="ty"><span></span><span></span><span></span></div></div>';msEl.appendChild(d);msEl.scrollTop=msEl.scrollHeight}
function etyp(){const e=document.getElementById('tp');if(e)e.remove()}
function snd(t){t=(t||inEl.value).trim();if(!t)return;inEl.value='';inEl.style.height='auto';sb.disabled=true;add(t,'u');styp();setTimeout(()=>{etyp();add(resp(t),'b');sb.disabled=false;inEl.focus()},400+Math.random()*300)}
sb.addEventListener('click',()=>snd());
inEl.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();snd()}});
inEl.addEventListener('input',()=>{inEl.style.height='auto';inEl.style.height=Math.min(inEl.scrollHeight,100)+'px'});
const ts=D.suburbs[0];
add(`<b>PropIQ ready</b> 🏠<br>Loaded <b>${D.total} Melbourne properties</b> across <b>${D.suburbs.length} suburbs</b>.<br>Top suburb: <b>${ts.suburb}</b> — score <b>${ts.sc.toFixed(4)}</b>.<br><br>What would you like to explore?`,'b');
</script></body></html>"""

build_ui()

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    if not OUT.exists():
        build_ui()
    return send_file(str(OUT), mimetype="text/html")

@app.route("/rebuild")
def rebuild():
    build_ui()
    return jsonify({"status": "ok"})

@app.route("/api/status")
def status():
    n = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM scores").fetchone()[0]
    return jsonify({"ok": True, "properties": n})

if __name__ == "__main__":
    print("\n  PropIQ -> http://localhost:8000\n")
    app.run(host="0.0.0.0", port=8000, debug=False)
