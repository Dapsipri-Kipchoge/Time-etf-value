import glob
import pandas as pd
import streamlit as st

st.set_page_config(page_title="TIME ETF 밸류 스크리너", layout="wide")
st.title("TIME ETF 국내 보유종목 밸류 스크리너")


@st.cache_data(ttl=1800)
def load():
    return pd.read_csv("data/result.csv", dtype={"종목코드": str})


try:
    df = load()
except FileNotFoundError:
    st.warning("data/result.csv 없음 — GitHub Actions를 먼저 실행하세요.")
    st.stop()

st.caption(f"기준일 {df['기준일'].iloc[0]} · 모집단 {len(df)}종목 · 출처: 타임폴리오 구성종목 + FnGuide 컨센서스 (개인용)")

# ── 사이드바 필터
with st.sidebar:
    st.header("필터")
    etfs = sorted({e for s in df["보유ETF"].dropna() for e in s.split(",")})
    sel = st.multiselect("ETF", etfs, default=etfs)
    only_pass = st.checkbox("1차 통과만", value=False)
    min_etf = st.slider("최소 보유 ETF 수", 1, int(df["보유ETF수"].max()), 1)
    if st.button("FnGuide 실시간 재수집 (느림)"):
        from fnguide import compute_stock
        with st.spinner("재수집 중…"):
            rows = []
            for _, r in df.iterrows():
                try:
                    d = compute_stock(r["종목코드"])
                except Exception as e:
                    d = {"종목코드": r["종목코드"], "기업": r["기업"], "비고": f"실패: {e}"}
                d.update(보유ETF수=r["보유ETF수"], 보유ETF=r["보유ETF"], 최대비중=r["최대비중"], 기준일="실시간")
                rows.append(d)
            df = pd.DataFrame(rows)

m = df["보유ETF"].fillna("").apply(lambda s: any(e in s.split(",") for e in sel)) & (df["보유ETF수"] >= min_etf)
if only_pass:
    m &= df["1차결과"].eq("통과")
v = df[m].copy()

COLS = ["기업", "보유ETF수", "최대비중", "fPOR", "fPER", "fPER(사이트)",
        "PEG(매출)1y", "PEG(영익)1y", "PEG(영익)2y", "PEG(영익)3y",
        "영업이익률(E)", "ROE(E)", "1차결과", "탈락조건", "비고"]
COLS = [c for c in COLS if c in v.columns]

st.subheader(f"스크리닝 표 ({len(v)}종목)")
st.dataframe(
    v[COLS].style.format({c: "{:.2f}" for c in COLS if v[c].dtype.kind == "f"}, na_rep="산출불가")
        .map(lambda x: "color:#1a7f37;font-weight:600" if x == "통과" else ("color:#b3261e" if x == "탈락" else ""),
             subset=["1차결과"] if "1차결과" in COLS else []),
    use_container_width=True, height=600, hide_index=True)

c1, c2, c3 = st.columns(3)
c1.metric("1차 통과", int(v["1차결과"].eq("통과").sum()))
c2.metric("PEG(영익)1y<0.5", int((v["PEG(영익)1y"] < 0.5).sum()))
c3.metric("컨센서스 없음", int(v["비고"].fillna("").str.contains("산출불가|실패").sum()))

with st.expander("1차 필터 기준"):
    st.markdown("""
국내 4조건 중 **2개 이상** 해당 시 탈락 (ROIC vs WACC는 미국주식 전용으로 제외)
1. PEG(영익) 3y→2y→1y 순으로 악화
2. PEG(영익) 1y ≥ 1.0
3. ROE(E) < 15%
4. 기저효과(전년 영익 ≤0 또는 영업이익률 <3%)로 PEG 왜곡, 3y PEG로도 보완 안 됨
""")

hist = sorted(glob.glob("data/result_*.csv"))
if len(hist) > 1:
    with st.expander(f"과거 스냅샷 ({len(hist)}개)"):
        pick = st.selectbox("날짜", hist[::-1])
        st.dataframe(pd.read_csv(pick, dtype={"종목코드": str})[COLS], hide_index=True)

st.download_button("CSV 다운로드", v.to_csv(index=False).encode("utf-8-sig"), "screen.csv")
