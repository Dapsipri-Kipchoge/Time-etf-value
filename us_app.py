import streamlit as st
from us_sectors import ORDER
from app_common import CSS, run

st.set_page_config(page_title="TIME ETF 밸류 스크리너 · 미장", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

US_CRITERIA = """
<div class="card"><div class="eyebrow">통과 기준 (미장 · 국장과 동일)</div>
<p style="margin:6px 0 10px">아래 <b>6개를 전부 충족</b>해야 통과. 섹터 구분 없이 동일 적용.</p>
<table class="t"><thead><tr><th class="l">지표</th><th>기준</th><th class="l">계산 (StockAnalysis 컨센서스, $)</th></tr></thead><tbody>
<tr><td class="l">PEG(매출) 1y</td><td>≤ 1.0</td><td class="l">fPER ÷ 매출증가율(FY0 확정 → FY1 추정, %)</td></tr>
<tr><td class="l">PEG(영익)</td><td>≤ 1.0</td><td class="l">fPER ÷ 영업이익증가율(1y). <b>기저효과</b>면 2y 기준으로 대체 — FY2 영업이익이 무료 데이터에 없어 <b>EPS 2y CAGR</b>로 대용</td></tr>
<tr><td class="l">ROE</td><td>≥ 10%</td><td class="l">최근 12개월 실적 ROE (추정 ROE 미제공)</td></tr>
<tr><td class="l">영업이익률(E)</td><td>≥ 10%</td><td class="l">FY1 영업이익 ÷ 매출</td></tr>
<tr><td class="l">fPER</td><td>≤ 30</td><td class="l">시가총액 ÷ FY1 순이익 (GAAP 기준 컨센)</td></tr>
<tr><td class="l">전년 영업이익률</td><td>≥ 5%</td><td class="l">FY0 확정 실적</td></tr>
</tbody></table></div>
<div class="card"><div class="eyebrow">국장과 다른 점</div>
<p style="margin:6px 0 0">① ROE가 추정치가 아니라 TTM 실적 ② PEG(영익) 2y가 EPS 기준 ③ 회계연도가 회사마다 달라(예: 엔비디아 1월 결산) FY1이 2026 또는 2027 ④ 참고 컬럼으로 <b>ROIC·WACC</b> 제공 — ROIC &lt; WACC면 자본비용을 못 버는 회사(기준에는 미포함) ⑤ ADR(TSM·ASML·BABA 등)은 미국 상장이면 포함</p></div>
<div class="card"><div class="eyebrow">판정 라벨 · 플래그 · 밸류점수</div>
<p style="margin:6px 0 0">국장과 동일. <span class="bd pass">통과</span> <span class="bd fail">탈락</span> <span class="bd hold">금융</span> <span class="bd keep">보류</span> · 플래그 <span class="bd flag">기저효과</span> <span class="bd flag">비지배괴리</span>(직접 fPER vs 사이트 Forward PE 30%↑ 차이 — non-GAAP EPS 기준 차이일 수 있음) · 밸류점수 = 모집단 백분위 가중합</p></div>
<div class="card"><div class="eyebrow">데이터</div>
<p style="margin:6px 0 0">모집단: 타임폴리오 해외 ETF 10종 구성종목 중 미국 상장 주식(… US EQUITY) 합집합 · 컨센서스·시총: StockAnalysis.com(S&P Global) Forecast·Statistics · 매 평일 18:30 KST 수집(미국 전일 종가 기준) · 단위 $M</p></div>
"""

run(dict(
    result="data/us_result.csv", holdings_glob="data/us_holdings_*.csv", watch="data/us_watchlist.csv",
    order=ORDER, mcap_col="시총($M)",
    eyebrow="TIME ETF · 해외 10종 · 미국 상장 보유종목 밸류 모니터", title="타임폴리오 보유종목 밸류 스크리너 — 미장",
    source_note="타임폴리오 해외 ETF 구성종목(US 상장) + StockAnalysis 컨센서스 · fPOR=시총÷영업이익(FY1) · fPER=시총÷순이익(FY1) · $M · 개인용",
    mc_slider_label="시총 상한($B, 0=제한 없음)", mc_slider_max=3000, mc_slider_step=50, mc_slider_mult=1000,
    criteria_html=US_CRITERIA,
))
