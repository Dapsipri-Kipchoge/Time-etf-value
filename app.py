import glob, os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="TIME ETF 밸류 스크리너", layout="wide")
st.title("TIME ETF 국내 보유종목 밸류 스크리너")

EXPAND, SHRINK = 0.10, -0.10   # 확대/축소 판정: 수량 ±10%


@st.cache_data(ttl=1800)
def load():
    res = pd.read_csv("data/result.csv", dtype={"종목코드": str})
    snaps = sorted(glob.glob("data/holdings_*.csv"))
    hold = {os.path.basename(p)[9:19]: pd.read_csv(p, dtype={"종목코드": str}) for p in snaps}
    return res, hold


try:
    df, hold = load()
except FileNotFoundError:
    st.warning("data/result.csv 없음 — GitHub Actions를 먼저 실행하세요.")
    st.stop()

dates = sorted(hold)
latest = hold[dates[-1]] if dates else pd.DataFrame()
prev = hold[dates[-2]] if len(dates) >= 2 else None

st.caption(f"기준일 {df['기준일'].iloc[0]} · 모집단 {len(df)}종목 · 출처: 타임폴리오 구성종목 + 네이버증권 컨센서스 (개인용) · "
           "fPOR=시총÷영업이익(E), fPER=시총÷순이익(E)")


# ───────── 공통: 변동 상태 계산
def diff_status(cur: pd.DataFrame, old: pd.DataFrame | None) -> pd.DataFrame:
    """ETF+종목코드 기준으로 직전 대비 상태/수량증감/비중증감 부여"""
    cur = cur.copy()
    if old is None:
        cur["상태"] = "—"; cur["수량증감"] = None; cur["비중증감"] = None
        return cur
    key = ["ETF", "종목코드"]
    m = cur.merge(old[key + ["수량", "비중"]], on=key, how="outer", suffixes=("", "_전"), indicator=True)
    m["상태"] = "유지"
    m.loc[m["_merge"] == "left_only", "상태"] = "신규"
    m.loc[m["_merge"] == "right_only", "상태"] = "제외"
    both = m["_merge"] == "both"
    chg = (m["수량"] - m["수량_전"]) / m["수량_전"].replace(0, pd.NA)
    m.loc[both & (chg >= EXPAND), "상태"] = "확대"
    m.loc[both & (chg <= SHRINK), "상태"] = "축소"
    m["수량증감"] = m["수량"] - m["수량_전"]
    m["비중증감"] = m["비중"] - m["비중_전"]
    # 제외 종목은 종목명이 비므로 old에서 보강
    if "종목명" in old.columns:
        names = old.set_index(key)["종목명"]
        m["종목명"] = m["종목명"].fillna(m.set_index(key).index.map(names))
    return m.drop(columns=["_merge"])


def style_status(x):
    return {"신규": "background:#1a7f37;color:white;font-weight:600",
            "확대": "color:#1a7f37;font-weight:600",
            "축소": "color:#b3261e;font-weight:600",
            "제외": "background:#b3261e;color:white;font-weight:600",
            "통과": "color:#1a7f37;font-weight:600", "탈락": "color:#b3261e",
            "판정보류": "color:#9a6700"}.get(x, "")


def fmt_table(v, cols):
    show = v[cols].copy()
    for c in cols:
        if show[c].dtype.kind in "fi":
            show[c] = show[c].map(lambda x: "산출불가" if pd.isna(x) else (f"{x:,.0f}" if c.startswith("수량") else f"{x:,.2f}"))
        else:
            show[c] = show[c].fillna("")
    sub = [c for c in ("상태", "1차결과") if c in cols]
    return show.style.map(style_status, subset=sub)


VAL_COLS = ["fPOR", "fPER", "fPER(사이트)", "PEG(매출)1y", "PEG(영익)1y", "PEG(영익)2y", "PEG(영익)3y",
            "영업이익률(E)", "ROE(E)", "1차결과", "탈락조건", "비고"]
VAL_COLS = [c for c in VAL_COLS if c in df.columns]

tab1, tab2, tab3 = st.tabs(["📊 밸류 스크리닝", "📁 ETF별 보유현황", "🔄 일일 변동"])

# ───────── 탭1: 기존 스크리닝
with tab1:
    c = st.columns([2, 1, 1])
    etfs = sorted({e for s in df["보유ETF"].dropna() for e in s.split(",")})
    sel = c[0].multiselect("ETF", etfs, default=etfs)
    only_pass = c[1].checkbox("1차 통과만")
    min_etf = c[2].slider("최소 보유 ETF 수", 1, int(df["보유ETF수"].max()), 1)
    m = df["보유ETF"].fillna("").apply(lambda s: any(e in s.split(",") for e in sel)) & (df["보유ETF수"] >= min_etf)
    if only_pass:
        m &= df["1차결과"].eq("통과")
    v = df[m]
    st.subheader(f"스크리닝 표 ({len(v)}종목)")
    st.dataframe(fmt_table(v, ["기업", "보유ETF수", "최대비중"] + VAL_COLS), use_container_width=True, height=560, hide_index=True)
    k = st.columns(4)
    k[0].metric("1차 통과", int(v["1차결과"].eq("통과").sum()))
    k[1].metric("PEG(영익)1y<0.5", int((v["PEG(영익)1y"] < 0.5).sum()))
    k[2].metric("판정보류", int(v["1차결과"].eq("판정보류").sum()))
    k[3].metric("컨센서스 없음", int(v["비고"].fillna("").str.contains("산출불가|실패").sum()))
    with st.expander("1차 필터 기준"):
        st.markdown("""
국내 4조건 중 **2개 이상** 해당 시 탈락 (ROIC vs WACC는 미국주식 전용)
1. PEG(영익) 3y→2y→1y 순으로 악화  2. PEG(영익)1y ≥ 1.0  3. ROE(E) < 15%
4. 기저효과(전년 영익 ≤0 또는 영업이익률 <3%)로 PEG 왜곡, 장기 PEG로도 보완 안 됨

**판정보류**: fPER 또는 PEG(영익) 전부 산출불가 (금융주는 매출·영업이익 행이 없어 해당)
""")
    st.download_button("CSV 다운로드", v.to_csv(index=False).encode("utf-8-sig"), "screen.csv")

# ───────── 탭2: ETF별
with tab2:
    if latest.empty:
        st.info("보유 스냅샷 없음 — 다음 수집부터 표시됩니다.")
    else:
        etf_list = sorted(latest["ETF"].unique())
        pick = st.radio("ETF", etf_list, horizontal=True, label_visibility="collapsed")
        cur = latest[latest["ETF"] == pick]
        old = prev[prev["ETF"] == pick] if prev is not None else None
        d = diff_status(cur, old)
        d = d.merge(df.drop(columns=["보유ETF", "보유ETF수", "최대비중", "기준일"], errors="ignore"), on="종목코드", how="left")
        d = d.sort_values("비중", ascending=False)
        head = st.columns(5)
        head[0].metric("보유종목", int((d["상태"] != "제외").sum()))
        for i, s_ in enumerate(["신규", "확대", "축소", "제외"], 1):
            head[i].metric(s_, int((d["상태"] == s_).sum()))
        st.caption(f"비교: {dates[-2] if prev is not None else '없음'} → {dates[-1]} · 확대/축소 = 수량 ±10%")
        cols = ["상태", "종목명", "종목코드", "수량", "수량증감", "비중", "비중증감"] + VAL_COLS
        st.dataframe(fmt_table(d, cols), use_container_width=True, height=620, hide_index=True)

# ───────── 탭3: 전 ETF 일일 변동
with tab3:
    if prev is None:
        st.info("비교할 직전 스냅샷이 없음 — 다음 수집일부터 변동이 표시됩니다.")
    else:
        allc = diff_status(latest, prev)
        chg = allc[allc["상태"].isin(["신규", "확대", "축소", "제외"])].copy()
        st.caption(f"{dates[-2]} → {dates[-1]} · 전 ETF 교차")
        c1, c2 = st.columns(2)
        buy = chg[chg["상태"].isin(["신규", "확대"])].groupby(["종목코드", "종목명"])["ETF"].agg(lambda s: ", ".join(sorted(s))).reset_index()
        sell = chg[chg["상태"].isin(["축소", "제외"])].groupby(["종목코드", "종목명"])["ETF"].agg(lambda s: ", ".join(sorted(s))).reset_index()
        c1.markdown(f"**🟢 매수 방향 (신규·확대) {len(buy)}종목**"); c1.dataframe(buy, hide_index=True, use_container_width=True)
        c2.markdown(f"**🔴 매도 방향 (축소·제외) {len(sell)}종목**"); c2.dataframe(sell, hide_index=True, use_container_width=True)
        st.subheader("변경 상세")
        cols = ["상태", "ETF", "종목명", "종목코드", "수량_전", "수량", "수량증감", "비중_전", "비중", "비중증감"]
        st.dataframe(fmt_table(chg.sort_values(["상태", "ETF"]), cols), use_container_width=True, height=500, hide_index=True)

    # 종목별 ETF 비중 피벗
    if not latest.empty:
        st.subheader("종목 × ETF 보유비중(%)")
        pv = latest.pivot_table(index=["종목코드", "종목명"], columns="ETF", values="비중", aggfunc="first")
        pv["보유ETF수"] = pv.notna().sum(axis=1)
        pv = pv.sort_values("보유ETF수", ascending=False).reset_index()
        q = st.text_input("종목 검색", "")
        if q:
            pv = pv[pv["종목명"].str.contains(q, case=False, na=False) | pv["종목코드"].str.contains(q)]
        st.dataframe(pv.style.format(precision=2, na_rep=""), use_container_width=True, height=500, hide_index=True)
