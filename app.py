import glob, os, html
import pandas as pd
import streamlit as st
from sectors import ORDER

st.set_page_config(page_title="TIME ETF 밸류 스크리너", layout="wide", initial_sidebar_state="collapsed")
EXPAND, SHRINK = 0.10, -0.10

# ───────────────────────── 디자인 토큰
CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
:root{--bg:#0B1220;--card:#121B2F;--line:#1F2B47;--txt:#E6EDF7;--mut:#8A97B0;--acc:#4C8DFF;
      --up:#2ED47A;--dn:#FF5C6C;--amb:#F5B942;--mono:'JetBrains Mono',ui-monospace,monospace;}
html,body,[class*="css"]{font-family:Pretendard,-apple-system,sans-serif;}
.stApp{background:var(--bg);color:var(--txt);}
.block-container{padding-top:1.2rem;max-width:1500px;}
h1,h2,h3{letter-spacing:-0.02em}
.eyebrow{font:600 11px var(--mono);letter-spacing:.18em;color:var(--acc);text-transform:uppercase}
.title{font-size:26px;font-weight:700;margin:2px 0 10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:12px}
.kpi{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:8px 0 14px}
.kpi .k{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--acc);border-radius:10px;padding:12px 14px}
.kpi .k.up{border-left-color:var(--up)} .kpi .k.dn{border-left-color:var(--dn)} .kpi .k.amb{border-left-color:var(--amb)}
.kpi .l{font-size:11px;color:var(--mut);letter-spacing:.06em} .kpi .v{font:600 24px var(--mono);margin-top:2px}
.kpi .s{font-size:11px;color:var(--mut);margin-top:2px}
.bd{display:inline-block;padding:2px 8px;border-radius:6px;font:600 11px var(--mono);letter-spacing:.02em}
.bd.new{background:var(--up);color:#04130a}.bd.exp{border:1px solid var(--up);color:var(--up)}
.bd.shr{border:1px solid var(--dn);color:var(--dn)}.bd.out{background:var(--dn);color:#fff}
.bd.keep{border:1px solid var(--line);color:var(--mut)}.bd.pass{border:1px solid var(--up);color:var(--up)}
.bd.fail{border:1px solid var(--dn);color:var(--dn)}.bd.hold{border:1px solid var(--amb);color:var(--amb)}
.bd.sec{background:#1B2A4A;color:#9FC0FF}.bd.flag{border:1px dashed var(--amb);color:var(--amb)}
table.t{width:100%;border-collapse:collapse;font-size:13px}
table.t th{position:sticky;top:0;background:#0F1728;color:var(--mut);font-weight:600;text-align:right;padding:8px 10px;border-bottom:1px solid var(--line);font-size:11.5px;letter-spacing:.04em;white-space:nowrap}
table.t th.l,table.t td.l{text-align:left}
table.t td{padding:7px 10px;border-bottom:1px solid #16203A;text-align:right;font-family:var(--mono);white-space:nowrap}
table.t td.l{font-family:Pretendard;font-weight:600}
table.t tr:hover td{background:#16213B}
.pos{color:var(--up)}.neg{color:var(--dn)}.na{color:#4C5875}
.scroll{max-height:620px;overflow:auto;border:1px solid var(--line);border-radius:10px}
.lead{display:grid;grid-template-columns:repeat(auto-fill,minmax(215px,1fr));gap:8px;margin-bottom:14px}
.lead .c{background:linear-gradient(160deg,#14203A,#0F1728);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.lead .c .s{font-size:11px;color:var(--acc);font-weight:700;letter-spacing:.04em}
.lead .c .n{font-size:15px;font-weight:700;margin:2px 0}
.lead .c .m{font:12px var(--mono);color:var(--mut)}
.bar{height:10px;background:#16203A;border-radius:6px;overflow:hidden;display:flex}
.bar i{display:block;height:100%}
.stTabs [data-baseweb="tab"]{font-weight:600;font-size:14px}
.stButton>button{background:var(--card);border:1px solid var(--line);color:var(--txt);border-radius:8px;font-size:12px;padding:4px 10px}
.stButton>button:hover{border-color:var(--dn);color:var(--dn)}
.note{font-size:12px;color:var(--mut)}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)


# ───────────────────────── 데이터
@st.cache_data(ttl=300)
def load():
    res = pd.read_csv("data/result.csv", dtype={"종목코드": str})
    snaps = sorted(glob.glob("data/holdings_*.csv"))
    hold = {os.path.basename(p)[9:19]: pd.read_csv(p, dtype={"종목코드": str}) for p in snaps}
    return res, hold


try:
    df, hold = load()
except FileNotFoundError:
    st.warning("data/result.csv 없음 — GitHub Actions를 먼저 실행하세요."); st.stop()

for c in ("섹터1", "섹터2"):
    if c not in df.columns: df[c] = "미분류"
for c, dflt in (("Type", "탈락"), ("플래그", ""), ("유효PEG", float("nan")), ("전년영업이익률", float("nan"))):
    if c not in df.columns: df[c] = dflt
for c in ("유효PEG", "fPER", "fPOR", "PEG(매출)1y", "PEG(영익)1y", "PEG(영익)2y", "ROE(E)", "영업이익률(E)", "매출증가율1y", "밸류점수" if "밸류점수" in df.columns else "fPER"):
    df[c] = pd.to_numeric(df[c], errors="coerce")
if "종목명" not in df.columns: df["종목명"] = df["기업"]
dates = sorted(hold); latest = hold[dates[-1]] if dates else pd.DataFrame()
prev = hold[dates[-2]] if len(dates) >= 2 else None


# ───────────────────────── 밸류점수 (전체 모집단 백분위, 낮을수록 좋은 지표는 반전)
def value_score(d: pd.DataFrame) -> pd.Series:
    ok = ~d["Type"].isin(["보류", "금융"]) & d["fPER"].notna()
    peg = d["유효PEG"].fillna(d["PEG(영익)1y"]).fillna(d["PEG(영익)2y"])
    comp = {
        "peg": (peg.where(peg > 0), False, .35), "fper": (d["fPER"].where(d["fPER"] > 0), False, .25),
        "roe": (d["ROE(E)"], True, .20), "opm": (d["영업이익률(E)"], True, .10), "g": (d["매출증가율1y"], True, .10)}
    score = pd.Series(0.0, index=d.index); wsum = pd.Series(0.0, index=d.index)
    for s, higher, w in comp.values():
        r = s[ok].rank(pct=True); r = r if higher else 1 - r
        score = score.add(r * w, fill_value=0); wsum = wsum.add(s.notna().astype(float) * w, fill_value=0)
    import numpy as np
    out = (score / wsum.replace(0, np.nan) * 100).astype(float).round(1)
    return out.where(ok)


df["밸류점수"] = value_score(df)


# ───────────────────────── 헬퍼
def badge(x):
    m = {"신규": "new", "확대": "exp", "축소": "shr", "제외": "out", "유지": "keep", "통과": "pass", "탈락": "fail", "판정보류": "hold",
         "보류": "keep", "금융": "hold"}
    return f'<span class="bd {m[x]}">{x}</span>' if x in m else html.escape(str(x)) if x == x else ""


def num(x, d=2, signed=False, suffix=""):
    if x is None or x != x: return '<span class="na">—</span>'
    s = f"{x:+,.{d}f}" if signed else f"{x:,.{d}f}"
    cls = "pos" if signed and x > 0 else "neg" if signed and x < 0 else ""
    return f'<span class="{cls}">{s}{suffix}</span>'


TBL_CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
:root{--bg:#0B1220;--card:#121B2F;--line:#1F2B47;--txt:#E6EDF7;--mut:#8A97B0;--acc:#4C8DFF;--up:#2ED47A;--dn:#FF5C6C;--amb:#F5B942;--mono:'JetBrains Mono',ui-monospace,monospace}
body{margin:0;background:transparent;color:var(--txt);font-family:Pretendard,-apple-system,sans-serif}
.wrap{border:1px solid var(--line);border-radius:10px;overflow:auto;height:calc(100vh - 4px);background:var(--bg)}
table.t{width:100%;border-collapse:collapse;font-size:13px}
table.t th{position:sticky;top:0;z-index:1;background:#0F1728;color:var(--mut);font-weight:600;text-align:right;padding:8px 10px;border-bottom:1px solid var(--line);font-size:11.5px;letter-spacing:.04em;white-space:nowrap;cursor:pointer;user-select:none}
table.t th:hover{color:var(--txt)} table.t th.on{color:var(--acc)}
table.t th.l,table.t td.l{text-align:left}
table.t td{padding:7px 10px;border-bottom:1px solid #16203A;text-align:right;font-family:var(--mono);white-space:nowrap}
table.t td.l{font-family:Pretendard;font-weight:600}
table.t tr:hover td{background:#16213B}
.pos{color:var(--up)}.neg{color:var(--dn)}.na{color:#4C5875}
.bd{display:inline-block;padding:2px 8px;border-radius:6px;font:600 11px var(--mono);letter-spacing:.02em;cursor:pointer}
.bd.new{background:var(--up);color:#04130a}.bd.exp{border:1px solid var(--up);color:var(--up)}
.bd.shr{border:1px solid var(--dn);color:var(--dn)}.bd.out{background:var(--dn);color:#fff}
.bd.keep{border:1px solid var(--line);color:var(--mut)}.bd.pass{border:1px solid var(--up);color:var(--up)}
.bd.fail{border:1px solid var(--dn);color:var(--dn)}.bd.hold{border:1px solid var(--amb);color:var(--amb)}
.bd.sec{background:#1B2A4A;color:#9FC0FF}.bd.flag{border:1px dashed var(--amb);color:var(--amb)}
.bd.active{outline:2px solid var(--acc);outline-offset:1px}
.hint{font:11px var(--mono);color:var(--mut);padding:6px 10px;position:sticky;left:0}
.hint b{color:var(--acc)}
"""
TBL_JS = """
<script>
(function(){
 const tbl=document.querySelector('table.t'), ths=[...tbl.tHead.rows[0].cells], body=tbl.tBodies[0], hint=document.getElementById('hint');
 let rows=[...body.rows], filt={}, sortCol=-1, asc=true;
 const keyOf=(tr,i)=>{const td=tr.cells[i]; const n=td.dataset.n; return n!==undefined? (n===''?null:parseFloat(n)) : td.textContent.trim();};
 function render(){
  let r=rows.filter(tr=>Object.entries(filt).every(([i,v])=>tr.cells[i].textContent.trim()===v));
  if(sortCol>=0){r.sort((a,b)=>{const x=keyOf(a,sortCol),y=keyOf(b,sortCol);
    if(x===null||x==='')return 1; if(y===null||y==='')return -1;
    if(typeof x==='number'&&typeof y==='number')return asc?x-y:y-x;
    return asc?String(x).localeCompare(String(y),'ko'):String(y).localeCompare(String(x),'ko');});}
  body.replaceChildren(...r);
  ths.forEach((th,i)=>{th.classList.toggle('on',i===sortCol); th.textContent=th.dataset.t+(i===sortCol?(asc?' ▲':' ▼'):'');});
  const f=Object.entries(filt).map(([i,v])=>ths[i].dataset.t+'='+v).join(', ');
  hint.innerHTML=r.length+'행'+(f?' · 필터 <b>'+f+'</b> (배지 다시 클릭 시 해제)':' · 머리글 클릭=정렬 · 배지 클릭=필터');
  document.querySelectorAll('.bd.active').forEach(e=>e.classList.remove('active'));
  Object.entries(filt).forEach(([i,v])=>r.forEach(tr=>{const b=tr.cells[i].querySelector('.bd'); if(b)b.classList.add('active');}));
 }
 ths.forEach((th,i)=>{th.dataset.t=th.textContent; th.onclick=()=>{if(sortCol===i)asc=!asc;else{sortCol=i;asc=true;} render();};});
 body.addEventListener('click',e=>{const b=e.target.closest('.bd'); if(!b)return; const td=b.closest('td'), i=td.cellIndex, v=b.textContent.trim();
   if(filt[i]===v)delete filt[i]; else filt[i]=v; render();});
 render();
})();
</script>"""


def table(d: pd.DataFrame, cols, fmt=None, height=620):
    import streamlit.components.v1 as components
    fmt = fmt or {}
    th = "".join(f'<th class="{"l" if c in LEFT else ""}">{html.escape(c)}</th>' for c in cols)
    rows = []
    for _, r in d.iterrows():
        tds = []
        for c in cols:
            v = r.get(c); data = ""
            if c in fmt: cell = fmt[c](v)
            elif c in ("상태", "1차결과", "일차", "이차", "Type"): cell = badge(v)
            elif c in ("섹터1", "섹터2"): cell = f'<span class="bd sec">{html.escape(str(v))}</span>'
            elif c == "플래그": cell = " ".join(f'<span class="bd flag">{html.escape(x)}</span>' for x in str(v).split(",") if x and x == x and x != "nan") if v == v and v else '<span class="na">—</span>'
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                cell = num(v, 0 if c.startswith("수량") else 2, signed=c.endswith("증감")); data = f' data-n="{"" if v != v else v}"'
            else: cell = html.escape("" if v != v or v is None else str(v))
            tds.append(f'<td class="{"l" if c in LEFT else ""}"{data}>{cell}</td>')
        rows.append("<tr>" + "".join(tds) + "</tr>")
    doc = f'<style>{TBL_CSS}</style><div class="wrap"><div class="hint" id="hint"></div><table class="t"><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{TBL_JS}'
    components.html(doc, height=height, scrolling=False)


LEFT = {"종목명", "기업", "종목코드", "ETF", "탈락조건", "비고", "섹터1", "섹터2", "보유ETF", "근거", "플래그", "섹터 대안", "메모"}


def kpis(items):
    h = "".join(f'<div class="k {c}"><div class="l">{l}</div><div class="v">{v}</div><div class="s">{s}</div></div>' for l, v, s, c in items)
    st.markdown(f'<div class="kpi">{h}</div>', unsafe_allow_html=True)


def diff_status(cur, old):
    cur = cur.copy()
    if old is None:
        cur["상태"] = "유지"; cur["수량증감"] = None; cur["비중증감"] = None; cur["수량_전"] = None; cur["비중_전"] = None
        return cur
    key = ["ETF", "종목코드"]
    m = cur.merge(old[key + ["종목명", "수량", "비중"]], on=key, how="outer", suffixes=("", "_전"), indicator=True)
    m["종목명"] = m["종목명"].fillna(m["종목명_전"])
    m["상태"] = "유지"
    m.loc[m["_merge"] == "left_only", "상태"] = "신규"; m.loc[m["_merge"] == "right_only", "상태"] = "제외"
    both = m["_merge"] == "both"; chg = (m["수량"] - m["수량_전"]) / m["수량_전"].replace(0, float("nan"))
    m.loc[both & (chg >= EXPAND), "상태"] = "확대"; m.loc[both & (chg <= SHRINK), "상태"] = "축소"
    m["수량증감"] = m["수량"] - m["수량_전"]; m["비중증감"] = m["비중"] - m["비중_전"]
    return m.drop(columns=["_merge", "종목명_전"])


VAL = ["Type", "fPOR", "fPER", "fPER(사이트)", "PEG(매출)1y", "PEG(영익)1y", "PEG(영익)2y", "유효PEG", "영업이익률(E)", "전년영업이익률", "ROE(E)", "밸류점수", "탈락조건", "플래그"]
VAL = [c for c in VAL if c in df.columns]

# ───────────────────────── 헤더
st.markdown('<div class="eyebrow">TIME ETF · 국내 8종 · 보유종목 밸류 모니터</div><div class="title">타임폴리오 보유종목 밸류 스크리너</div>', unsafe_allow_html=True)
st.markdown(f'<div class="note">기준일 {df["기준일"].iloc[0]} · 모집단 {len(df)}종목 · 타임폴리오 구성종목 + 네이버증권 컨센서스 · fPOR=시총÷영업이익(E) · fPER=시총÷순이익(E) · 개인용</div>', unsafe_allow_html=True)

T = st.tabs(["밸류 스크리닝", "포트폴리오 제안", "ETF별 보유현황", "일일 변동", "워치리스트", "기준 설명"])

# ═════════ 1. 스크리닝
with T[0]:
    c = st.columns([2, 2, 1, 1])
    etfs = sorted({e for s in df["보유ETF"].dropna() for e in s.split(",")})
    sel = c[0].multiselect("ETF", etfs, default=etfs)
    secs = c[1].multiselect("섹터", [s for s in ORDER if s in set(df["섹터1"])], default=[])
    types = c[2].multiselect("판정", ["통과", "탈락", "금융", "보류"], default=["통과", "탈락"]); sort = c[3].selectbox("기본 정렬", ["Type", "밸류점수", "유효PEG", "fPER", "ROE(E)", "최대비중"])
    m = df["보유ETF"].fillna("").apply(lambda s: any(e in s.split(",") for e in sel))
    if secs: m &= df["섹터1"].isin(secs)
    m &= df["Type"].isin(types)
    v = df[m].sort_values(sort, ascending=sort in ("유효PEG", "fPER", "Type"), na_position="last")
    T_ = df[df["보유ETF"].fillna("").apply(lambda s: any(e in s.split(",") for e in sel))]
    kpis([("표시", len(v), "필터 적용", ""), ("통과", int(T_["Type"].eq("통과").sum()), "6개 기준 전부 충족", "up"),
          ("탈락", int(T_["Type"].eq("탈락").sum()), "1개 이상 미달", "dn"),
          ("금융", int(T_["Type"].eq("금융").sum()), "기준 미적용 · 별도 판단", "amb"),
          ("보류", int(T_["Type"].eq("보류").sum()), "컨센서스 없음", "")])
    table(v, ["종목명", "섹터1", "보유ETF수", "최대비중"] + VAL)
    st.download_button("CSV 다운로드", v.to_csv(index=False).encode("utf-8-sig"), "screen.csv")

# ═════════ 2. 포트폴리오 제안
with T[1]:
    c = st.columns(4)
    n = c[0].slider("종목 수", 5, 15, 10); per_sec = c[1].slider("섹터당 최대 종목", 1, 3, 2)
    cap = c[2].slider("섹터 비중 상한(%)", 15, 40, 25); style = c[3].selectbox("성향", ["균형", "성장(PEG 중심)", "퀄리티(ROE 중심)"])
    passed = df[(df["Type"] == "통과") & df["밸류점수"].notna()]
    if "excl" not in st.session_state: st.session_state.excl = []
    c = st.columns([3, 1])
    mc_max_t = c[1].slider("시총 상한(조원, 0=제한 없음)", 0, 500, 0, step=5)
    if st.session_state.excl:
        chips = " ".join(f'<span class="bd fail">{html.escape(x)}</span>' for x in st.session_state.excl)
        c[0].markdown(f'<div class="note" style="margin-top:28px">제외 중: {chips}</div>', unsafe_allow_html=True)
        if c[0].button("제외 초기화", key="excl_reset"): st.session_state.excl = []; st.rerun()
    else:
        c[0].markdown('<div class="note" style="margin-top:34px">표 아래 ✕ 버튼으로 종목을 빼면 같은 섹터의 다음 후보로 자동 재구성됨</div>', unsafe_allow_html=True)
    cand = passed[~passed["종목명"].isin(st.session_state.excl)].copy()
    if mc_max_t: cand = cand[cand["시총(억)"].fillna(0) <= mc_max_t * 10000]
    cand["티어"] = 1
    if style == "성장(PEG 중심)": cand["정렬"] = cand["밸류점수"] - cand["PEG(영익)1y"].fillna(cand["PEG(영익)2y"]).fillna(1) * 20
    elif style == "퀄리티(ROE 중심)": cand["정렬"] = cand["밸류점수"] + cand["ROE(E)"].fillna(0) * 0.5
    else: cand["정렬"] = cand["밸류점수"] + cand["보유ETF수"] * 3       # ETF 다수 보유 = 운용사 확신 가점
    cand = cand.sort_values(["티어", "정렬"], ascending=False)
    picks, cnt = [], {}
    for _, r in cand.iterrows():
        if cnt.get(r["섹터1"], 0) >= per_sec: continue
        picks.append(r); cnt[r["섹터1"]] = cnt.get(r["섹터1"], 0) + 1
        if len(picks) >= n: break
    P = pd.DataFrame(picks)
    if P.empty:
        st.info("통과 종목이 없음 — 기준을 전부 충족하는 종목이 나올 때까지 빈 상태로 둠")
    else:
        w = P["정렬"].clip(lower=1); w = w / w.sum()
        for _ in range(10):                                              # 섹터 상한 적용
            sw = w.groupby(P["섹터1"]).transform("sum"); over = sw > cap / 100
            if not over.any(): break
            w[over] *= (cap / 100) / sw[over]; w[~over] *= (1 - w[over].sum()) / w[~over].sum()
        P["비중(%)"] = (w * 100).round(1)
        picked = set(P["종목명"])
        def _alt(r):
            a = cand[(cand["섹터1"] == r["섹터1"]) & ~cand["종목명"].isin(picked)].head(2)
            return " / ".join(f'{x["종목명"]}({x["밸류점수"]:.0f})' for _, x in a.iterrows()) or "—"
        P["섹터 대안"] = P.apply(_alt, axis=1)
        P["근거"] = P.apply(lambda r: " · ".join(x for x in [
            f'PEG {r["유효PEG"]:.2f}' if pd.notna(r["유효PEG"]) else None,
            f'fPER {r["fPER"]:.1f}' if pd.notna(r["fPER"]) else None, f'ROE {r["ROE(E)"]:.0f}%' if pd.notna(r["ROE(E)"]) else None,
            f'{int(r["보유ETF수"])}개 ETF 보유'] if x), axis=1)
        alloc = P.groupby("섹터1")["비중(%)"].sum().sort_values(ascending=False)
        pal = ["#4C8DFF", "#2ED47A", "#F5B942", "#FF5C6C", "#9B7BFF", "#2FC6D6", "#FF9F5A", "#7DD3FC", "#C084FC", "#A3E635"]
        bar = "".join(f'<i style="width:{v}%;background:{pal[i % len(pal)]}" title="{k} {v:.0f}%"></i>' for i, (k, v) in enumerate(alloc.items()))
        leg = " &nbsp; ".join(f'<span style="color:{pal[i % len(pal)]}">■</span> {k} {v:.0f}%' for i, (k, v) in enumerate(alloc.items()))
        kpis([("종목", len(P), f"{style} · 통과 {len(cand)}개 중", ""), ("섹터 수", len(alloc), f"상한 {cap}%", "up"),
              ("가중 fPER", f'{(P["fPER"] * w).sum():.1f}', "비중가중", "amb"),
              ("가중 ROE", f'{(P["ROE(E)"].fillna(0) * w).sum():.0f}%', "비중가중", "amb")])
        st.markdown(f'<div class="card"><div class="note" style="margin-bottom:6px">섹터 배분</div><div class="bar">{bar}</div><div class="note" style="margin-top:8px">{leg}</div></div>', unsafe_allow_html=True)
        table(P, ["Type", "종목명", "섹터1", "비중(%)", "밸류점수", "fPER", "유효PEG", "ROE(E)", "시총(억)", "보유ETF수", "플래그", "근거", "섹터 대안"], height=520)
        bc = st.columns(min(len(P), 5))
        for i, (_, r) in enumerate(P.iterrows()):
            if bc[i % len(bc)].button(f"✕ {r['종목명']}", key=f"ex_{r['종목코드']}", help=f"{r['섹터1']} · 대안: {r['섹터 대안']}"):
                st.session_state.excl.append(r["종목명"]); st.rerun()
        if len(P) < n: st.markdown(f'<div class="note">통과 종목이 {len(P)}개라 {n}개를 채우지 못함 — 기준 완화 없이 그대로 표시</div>', unsafe_allow_html=True)
        st.markdown('<div class="note">통과 종목만으로 규칙 구성(밸류점수·섹터 분산)이며 투자 권유가 아님.</div>', unsafe_allow_html=True)

# ═════════ 3. ETF별
with T[2]:
    if latest.empty: st.info("보유 스냅샷 없음 — 다음 수집부터 표시됩니다.")
    else:
        pick = st.radio("ETF", sorted(latest["ETF"].unique()), horizontal=True, label_visibility="collapsed")
        d = diff_status(latest[latest["ETF"] == pick], prev[prev["ETF"] == pick] if prev is not None else None)
        d = d.merge(df.drop(columns=["보유ETF", "보유ETF수", "최대비중", "기준일", "종목명"], errors="ignore"), on="종목코드", how="left").sort_values("비중", ascending=False)
        kpis([("보유종목", int((d["상태"] != "제외").sum()), f'{dates[-2] if prev is not None else "—"} → {dates[-1]}', ""),
              ("신규", int((d["상태"] == "신규").sum()), "편입", "up"), ("확대", int((d["상태"] == "확대").sum()), "수량 +10%↑", "up"),
              ("축소", int((d["상태"] == "축소").sum()), "수량 −10%↓", "dn"), ("제외", int((d["상태"] == "제외").sum()), "전량 매도", "dn")])
        table(d, ["상태", "종목명", "섹터1", "Type", "수량", "수량증감", "비중", "비중증감", "밸류점수", "fPOR", "fPER", "유효PEG", "ROE(E)", "플래그"])

# ═════════ 4. 일일 변동
with T[3]:
    if prev is None: st.info("직전 스냅샷이 없음 — 다음 수집일부터 신규·확대·축소·제외가 표시됩니다.")
    else:
        allc = diff_status(latest, prev); chg = allc[allc["상태"].isin(["신규", "확대", "축소", "제외"])].copy()
        chg = chg.merge(df[["종목코드", "섹터1"]], on="종목코드", how="left")
        buy = chg[chg["상태"].isin(["신규", "확대"])].groupby("종목명")["ETF"].agg(lambda s: ", ".join(sorted(s)))
        sell = chg[chg["상태"].isin(["축소", "제외"])].groupby("종목명")["ETF"].agg(lambda s: ", ".join(sorted(s)))
        st.markdown(f'<div class="note">{dates[-2]} → {dates[-1]} · 전 ETF 교차 · 수량 기준</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="card" style="border-left:4px solid var(--up)"><b>매수 방향 (신규·확대)</b> <span class="note">{len(buy)}종목</span><br>' +
                    "<br>".join(f'<b>{html.escape(k)}</b> <span class="note">{html.escape(v)}</span>' for k, v in buy.items()) + "</div>", unsafe_allow_html=True)
        c2.markdown(f'<div class="card" style="border-left:4px solid var(--dn)"><b>매도 방향 (축소·제외)</b> <span class="note">{len(sell)}종목</span><br>' +
                    "<br>".join(f'<b>{html.escape(k)}</b> <span class="note">{html.escape(v)}</span>' for k, v in sell.items()) + "</div>", unsafe_allow_html=True)
        table(chg.sort_values(["상태", "ETF"]), ["상태", "ETF", "종목명", "섹터1", "수량_전", "수량", "수량증감", "비중_전", "비중", "비중증감"], height=500)
    if not latest.empty:
        st.markdown('<div class="note" style="margin-top:14px">종목 × ETF 보유비중(%)</div>', unsafe_allow_html=True)
        pv = latest.pivot_table(index=["종목코드", "종목명"], columns="ETF", values="비중", aggfunc="first")
        pv["보유ETF수"] = pv.notna().sum(axis=1); pv = pv.sort_values("보유ETF수", ascending=False).reset_index()
        q = st.text_input("종목 검색", "", placeholder="종목명 또는 코드")
        if q: pv = pv[pv["종목명"].str.contains(q, case=False, na=False) | pv["종목코드"].str.contains(q)]
        table(pv, list(pv.columns), height=500)


# ═════════ 5. 워치리스트
with T[4]:
    try:
        W = pd.read_csv("data/watchlist.csv", dtype={"종목코드": str})
        for c in ("유효PEG", "fPER", "fPOR", "PEG(매출)1y", "PEG(영익)1y", "PEG(영익)2y", "ROE(E)", "영업이익률(E)", "전년영업이익률", "매출증가율1y", "시총(억)"):
            if c in W.columns: W[c] = pd.to_numeric(W[c], errors="coerce")
        for c, dflt in (("Type", "탈락"), ("플래그", ""), ("메모", "")):
            if c not in W.columns: W[c] = dflt
        st.markdown('<div class="note">타임폴리오 모집단과 별개로 수기 관리하는 관심종목 · 같은 6개 기준으로 판정 · 매일 함께 수집</div>', unsafe_allow_html=True)
        kpis([("종목", len(W), "워치리스트", ""), ("통과", int(W["Type"].eq("통과").sum()), "6개 기준 전부", "up"),
              ("탈락", int(W["Type"].eq("탈락").sum()), "", "dn")])
        table(W, ["종목명", "섹터1", "Type", "현재가", "시총(억)", "fPOR", "fPER", "fPER(사이트)", "PEG(매출)1y", "유효PEG",
                  "영업이익률(E)", "전년영업이익률", "ROE(E)", "매출증가율1y", "탈락조건", "플래그", "메모"], height=300)
    except FileNotFoundError:
        st.info("data/watchlist.csv 없음 — 다음 수집부터 표시됩니다.")

# ═════════ 6. 기준 설명
with T[5]:
    st.markdown("""
<div class="card"><div class="eyebrow">통과 기준</div>
<p style="margin:6px 0 10px">아래 <b>6개를 전부 충족</b>해야 통과. 섹터 구분 없이 동일 적용. 부족하다고 완화하지 않음.</p>
<table class="t"><thead><tr><th class="l">지표</th><th>기준</th><th class="l">계산</th></tr></thead><tbody>
<tr><td class="l">PEG(매출) 1y</td><td>≤ 1.0</td><td class="l">fPER ÷ 매출증가율(전년 → 당해E, %)</td></tr>
<tr><td class="l">PEG(영익)</td><td>≤ 1.0</td><td class="l">fPER ÷ 영업이익증가율(1y). <b>기저효과</b>면 2y CAGR 기준으로 대체</td></tr>
<tr><td class="l">ROE(E)</td><td>≥ 10%</td><td class="l">네이버 당해 추정 ROE(지배주주)</td></tr>
<tr><td class="l">영업이익률(E)</td><td>≥ 10%</td><td class="l">당해E 영업이익 ÷ 매출</td></tr>
<tr><td class="l">fPER</td><td>≤ 30</td><td class="l">시가총액 ÷ 당해E 순이익</td></tr>
<tr><td class="l">전년 영업이익률</td><td>≥ 5%</td><td class="l"><b>확정 실적</b> 기준(직전 회계연도). 컨센만 좋은 턴어라운드 스토리를 거르는 유일한 과거 지표</td></tr>
</tbody></table></div>

<div class="card"><div class="eyebrow">기저효과 규칙</div>
<p style="margin:6px 0 0">전년 영업이익 ≤ 0, 전년 영업이익률 &lt; 3%, 또는 당해 영익증가율 &gt; 150% 중 하나면 1년 성장률이 왜곡된 것으로 보고 PEG(영익)을 <b>2년 CAGR</b>로 계산. 플래그 <span class="bd flag">기저효과</span> 표시.</p></div>

<div class="card"><div class="eyebrow">판정 라벨</div>
<p style="margin:6px 0 0"><span class="bd pass">통과</span> 5개 전부 충족 &nbsp; <span class="bd fail">탈락</span> 1개 이상 미달(탈락조건 칸에 사유) &nbsp; <span class="bd hold">금융</span> 은행·증권·보험은 영업이익·PEG 개념이 달라 기준 미적용, 별도 판단 &nbsp; <span class="bd keep">보류</span> 컨센서스 없음</p></div>

<div class="card"><div class="eyebrow">플래그 (탈락 사유 아님)</div>
<p style="margin:6px 0 0"><b>기저효과</b> 위 규칙 해당 · <b>비지배괴리</b> 직접 계산 fPER과 네이버 PER(E)가 30% 이상 차이 — 비지배지분·EPS 기준 차이 가능성, 수기 확인 권장</p></div>

<div class="card"><div class="eyebrow">밸류점수 (0~100, 정렬용)</div>
<p style="margin:6px 0 0">모집단 전체 백분위 가중합: 유효PEG 35% · fPER 25% · ROE 20% · 영업이익률 10% · 매출성장 10%. 상대 점수라 통과/탈락과 무관하며 <b>같은 통과 종목끼리 줄 세우는 용도</b>.</p></div>

<div class="card"><div class="eyebrow">데이터</div>
<p style="margin:6px 0 0">모집단: 타임폴리오 국내 ETF 8종 구성종목 합집합(현금·ETF 제외), 매 평일 18:30 수집 · 컨센서스·시총: 네이버증권 기업실적분석 표(당해E) · fPOR = 시총 ÷ 영업이익(E)</p></div>
""", unsafe_allow_html=True)
