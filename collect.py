"""
타임폴리오 국내 ETF 8종 보유종목(합집합) → FnGuide CompanyGuide 컨센서스 → data/*.csv
실행: python collect.py
"""
import io, os, re, time, datetime as dt
import requests, pandas as pd
from bs4 import BeautifulSoup

from fnguide import compute_stock

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIME_ETFS = {  # idx: (ETF코드, 이름)  — timeetf.co.kr/m11_list.php?cate=002
    12: ("441800", "Korea플러스배당"), 11: ("385720", "코스피"),
    15: ("495060", "코리아밸류업"),    24: ("0162Y0", "코스닥"),
    16: ("404120", "K신재생에너지"),    13: ("463050", "K바이오"),
    17: ("385710", "K이노베이션"),      1:  ("410870", "K컬처"),
}
VIEW = "https://timeetf.co.kr/m11_view.php?idx={idx}&cate=002"


def etf_holdings(idx: int) -> pd.DataFrame:
    """종목코드/종목명/비중 — 표가 JS로 채워지므로 headless 크롬으로 렌더링 후 파싱"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA["User-Agent"])
        pg.goto(VIEW.format(idx=idx), wait_until="networkidle", timeout=60000)
        pg.wait_for_selector("#constituentItems table tbody tr, table:has-text('종목코드') tbody tr", timeout=30000)
        for _ in range(30):                                   # 더보기 버튼 모두 펼치기
            btn = pg.query_selector("#constituentItems :text('더보기'), a:has-text('더보기'), button:has-text('더보기')")
            if not btn or not btn.is_visible():
                break
            try:
                btn.click(); pg.wait_for_timeout(400)
            except Exception:
                break
        html = pg.content()
        b.close()
    df = None
    for t in pd.read_html(io.StringIO(html)):
        cols = "".join(map(str, t.columns))
        if "종목코드" in cols and len(t) > 0:
            df = t
            break
    if df is None:
        raise RuntimeError(f"ETF idx={idx} 구성종목 표 없음/빈 표")
    print(f"  [debug] idx={idx} columns={list(df.columns)} rows={len(df)}")
    df.columns = [re.sub(r"\s+", "", str(c)) for c in df.columns]
    wcol = next(c for c in df.columns if c.startswith("비중"))
    qcol = next((c for c in df.columns if c.startswith("수량")), None)
    df = df.rename(columns={wcol: "비중", qcol: "수량"} if qcol else {wcol: "비중"})
    if "수량" not in df.columns:
        df["수량"] = None
    df = df[["종목코드", "종목명", "수량", "비중"]]
    def norm(x):  # 5930.0 / 5930 / "005930" → "005930"
        s = str(x).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s.zfill(6) if s.isdigit() else s
    df["종목코드"] = df["종목코드"].map(norm)
    df = df[df["종목코드"].str.fullmatch(r"[0-9A-Z]{6}") & df["종목코드"].str[0].str.isdigit()]
    df = df[~df["종목명"].astype(str).str.contains("ETF|KODEX|TIGER|채권|선물|현금", na=False)]
    df["비중"] = pd.to_numeric(df["비중"], errors="coerce")
    df["수량"] = pd.to_numeric(df["수량"].astype(str).str.replace(",", ""), errors="coerce")
    return df


def build_universe():
    frames = []
    for idx, (ecode, ename) in TIME_ETFS.items():
        try:
            h = etf_holdings(idx)
            h["ETF"] = ename
            frames.append(h)
            print(f"[ETF] {ename}: {len(h)}종목")
        except Exception as e:
            print(f"[ETF] {ename} 실패: {e}")
        time.sleep(1)
    all_ = pd.concat(frames)[["ETF", "종목코드", "종목명", "수량", "비중"]]
    uni = (all_.groupby(["종목코드", "종목명"])
           .agg(보유ETF수=("ETF", "nunique"),
                보유ETF=("ETF", lambda s: ",".join(sorted(set(s)))),
                최대비중=("비중", "max"))
           .reset_index()
           .sort_values(["보유ETF수", "최대비중"], ascending=False))
    return uni, all_


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    today = dt.date.today().isoformat()
    uni, holdings = build_universe()
    uni.to_csv("data/universe.csv", index=False, encoding="utf-8-sig")
    holdings["기준일"] = today
    holdings.to_csv("data/holdings.csv", index=False, encoding="utf-8-sig")
    holdings.to_csv(f"data/holdings_{today}.csv", index=False, encoding="utf-8-sig")
    print(f"모집단 {len(uni)}종목")

    rows = []
    for i, r in uni.iterrows():
        try:
            d = compute_stock(r["종목코드"])
        except Exception as e:
            d = {"종목코드": r["종목코드"], "기업": r["종목명"], "비고": f"실패: {e}"}
        d.update(보유ETF수=r["보유ETF수"], 보유ETF=r["보유ETF"], 최대비중=r["최대비중"])
        rows.append(d)
        print(f"  {r['종목명']}: {d.get('비고', 'ok')}")
        time.sleep(1.5)                                         # 차단 방지

    out = pd.DataFrame(rows)
    out["기준일"] = today
    out.to_csv("data/result.csv", index=False, encoding="utf-8-sig")
    out.to_csv(f"data/result_{today}.csv", index=False, encoding="utf-8-sig")
    print("완료")
