"""타임폴리오 해외 ETF 10종 → 미국 상장 종목(… US EQUITY)만 합집합 → StockAnalysis → data/us_*.csv"""
import io, os, re, time, datetime as dt
import pandas as pd
from fnguide import screen
from stockanalysis import compute_us, fetch_industry
from us_sectors import classify

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TIME_US_ETFS = {  # idx: 이름
    25: "글로벌휴머노이드로봇", 2: "미국나스닥100", 5: "미국S&P500", 22: "글로벌탑픽", 6: "글로벌AI인공지능",
    9: "글로벌바이오", 20: "글로벌우주테크&방산", 19: "차이나AI테크", 10: "나스닥100채권혼합50", 8: "글로벌소비트렌드",
}
VIEW = "https://timeetf.co.kr/m11_view.php?idx={idx}&cate=001"

# 미국 상장이지만 미국 기업이 아닌 ADR/외국적 기업 — 모집단에서 제외
EXCLUDE_FOREIGN = {"TSM", "ASML", "BABA", "PDD", "ARM", "SAP", "SKHY", "TSEM", "NBIS", "SE", "SNY", "NVO", "AZN", "SHOP", "SPOT", "TM", "SONY", "UMC", "GRAB", "CPNG", "JD", "BIDU", "NTES", "TCOM", "LI", "XPEV", "NIO", "ZK", "HMC", "MUFG", "SMFG", "IBN", "HDB", "INFY", "WIT", "RIO", "BHP", "VALE", "SCCO"}


def etf_holdings(idx):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(user_agent=UA)
        pg.goto(VIEW.format(idx=idx), wait_until="networkidle", timeout=60000)
        pg.wait_for_selector("table:has-text('종목코드') tbody tr", timeout=30000)
        for _ in range(30):
            btn = pg.query_selector("#constituentItems :text('더보기'), a:has-text('더보기'), button:has-text('더보기')")
            if not btn or not btn.is_visible(): break
            try: btn.click(); pg.wait_for_timeout(400)
            except Exception: break
        html = pg.content(); b.close()
    df = None
    for t in pd.read_html(io.StringIO(html)):
        if "종목코드" in "".join(map(str, t.columns)) and len(t) > 0:
            df = t; break
    if df is None: raise RuntimeError(f"idx={idx} 표 없음")
    df.columns = [re.sub(r"\s+", "", str(c)) for c in df.columns]
    wcol = next(c for c in df.columns if c.startswith("비중")); qcol = next((c for c in df.columns if c.startswith("수량")), None)
    df = df.rename(columns={wcol: "비중", **({qcol: "수량"} if qcol else {})})
    if "수량" not in df.columns: df["수량"] = None
    df["종목코드"] = df["종목코드"].astype(str).str.strip()
    us = df[df["종목코드"].str.upper().str.endswith(" US EQUITY")].copy()            # 미국 상장만
    us["종목코드"] = us["종목코드"].str.upper().str.replace(" US EQUITY", "", regex=False).str.replace("/", "-").str.replace(".", "-")
    us = us[~us["종목명"].astype(str).str.contains("ETF|E-MINI|INDEX|FUTURE|TRUST", case=False, na=False)]
    us["비중"] = pd.to_numeric(us["비중"], errors="coerce")
    us["수량"] = pd.to_numeric(us["수량"].astype(str).str.replace(",", ""), errors="coerce")
    return us[["종목코드", "종목명", "수량", "비중"]]


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True); today = dt.date.today().isoformat()
    frames = []
    for idx, name in TIME_US_ETFS.items():
        try:
            h = etf_holdings(idx); h["ETF"] = name; frames.append(h); print(f"[ETF] {name}: US {len(h)}종목")
        except Exception as e:
            print(f"[ETF] {name} 실패: {e}")
        time.sleep(1)
    hold = pd.concat(frames)[["ETF", "종목코드", "종목명", "수량", "비중"]]
    hold["기준일"] = today
    hold.to_csv("data/us_holdings.csv", index=False, encoding="utf-8-sig")
    hold.to_csv(f"data/us_holdings_{today}.csv", index=False, encoding="utf-8-sig")
    n0 = hold["종목코드"].nunique()
    hold = hold[~hold["종목코드"].isin(EXCLUDE_FOREIGN)]
    print(f"외국적 ADR 제외: {n0 - hold['종목코드'].nunique()}종목")
    uni = (hold.groupby("종목코드").agg(종목명=("종목명", "first"), 보유ETF수=("ETF", "nunique"),
                                       보유ETF=("ETF", lambda s: ",".join(sorted(set(s)))), 최대비중=("비중", "max"))
           .reset_index().sort_values(["보유ETF수", "최대비중"], ascending=False))
    uni.to_csv("data/us_universe.csv", index=False, encoding="utf-8-sig")
    print(f"모집단 {len(uni)}종목")

    rows = []
    for _, r in uni.iterrows():
        t = r["종목코드"]
        try:
            d = compute_us(t.lower())
            d["종목코드"] = t
        except Exception as e:
            d = {"종목코드": t, "기업": r["종목명"], "비고": f"실패: {e}"}
        ind = fetch_industry(t.lower())
        d["섹터1"], d["섹터2"] = classify(t, ind)
        if d.get("통화", "USD") != "USD":                     # 안전망: 재무통화가 USD가 아니면 외국 기업으로 보고 제외
            print(f"  {t}: 제외 (재무통화 {d['통화']})"); time.sleep(1.2); continue
        d["종목명"] = r["종목명"]
        d.update(보유ETF수=r["보유ETF수"], 보유ETF=r["보유ETF"], 최대비중=r["최대비중"])
        d = screen(d, d["섹터1"])
        rows.append(d); print(f"  {t}: {d.get('Type')} {d.get('비고','')}")
        time.sleep(1.2)
    out = pd.DataFrame(rows); out["기준일"] = today
    out.to_csv("data/us_result.csv", index=False, encoding="utf-8-sig")
    out.to_csv(f"data/us_result_{today}.csv", index=False, encoding="utf-8-sig")
    print("완료")
