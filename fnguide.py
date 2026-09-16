"""네이버증권 컨센서스 수집 + 스크리닝 판정
데이터 소스(2026-09 개편 이후): 모바일 네이버증권 JSON API
  - https://m.stock.naver.com/api/stock/{code}/finance/annual   연간 재무·컨센서스 (단위 억원, isConsensus="Y"가 추정치)
  - https://m.stock.naver.com/api/stock/{code}/basic            종목명·현재가
  - https://m.stock.naver.com/api/stock/{code}/integration      시가총액·업종
정의:
  fPOR = 시가총액 ÷ 당해(E) 영업이익
  fPER = 시가총액 ÷ 당해(E) 지배주주순이익   (지배주주 없으면 당기순이익으로 대체, 비고 표시)
"""
import re
import requests
import pandas as pd

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
           "Accept": "application/json, text/plain, */*", "Accept-Language": "ko-KR,ko;q=0.9"}
M_BASIC = "https://m.stock.naver.com/api/stock/{code}/basic"
M_INTEG = "https://m.stock.naver.com/api/stock/{code}/integration"
M_ANNUAL = "https://m.stock.naver.com/api/stock/{code}/finance/annual"
M_REFERER = "https://m.stock.naver.com/domestic/stock/{code}/total"

ITEMS = {"매출액", "영업이익", "당기순이익", "지배주주순이익", "ROE", "PER", "주당배당금", "부채비율"}


# ───────────────────────── 유틸
def to_num(x):
    s = str(x).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "nan", "None", "N/A", "null"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _clean_title(t):
    return re.sub(r"\s|\(.*?\)", "", str(t))          # "ROE(지배주주)" → "ROE"


def _walk(obj):
    yield obj
    if isinstance(obj, dict):
        for v in obj.values(): yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj: yield from _walk(v)


def _api_json(url, code):
    h = {**HEADERS, "Referer": M_REFERER.format(code=code)}
    r = requests.get(url.format(code=code), headers=h, timeout=15)
    r.raise_for_status()
    return r.json()


def cagr(cur, base, n):
    if cur is None or base is None or base <= 0 or cur <= 0:
        return None
    return ((cur / base) ** (1 / n) - 1) * 100


def peg(fper, g):
    return None if fper is None or g is None or g <= 0 else fper / g


# ───────────────────────── 수집
def fetch_finance(code) -> pd.DataFrame:
    """연간 재무 → DataFrame(index=항목, columns='2026.12(E)' 형식)"""
    j = _api_json(M_ANNUAL, code)
    fi = j.get("financeInfo") if isinstance(j, dict) and isinstance(j.get("financeInfo"), dict) else (j if isinstance(j, dict) else {})
    trs = {str(t.get("key")): t for t in (fi.get("trTitleList") or []) if isinstance(t, dict)}

    def label(key):
        key = str(key); t = trs.get(key, {})
        ttl = str(t.get("title") or "").rstrip(".")
        if not re.fullmatch(r"\d{4}\.\d{2}", ttl):
            ttl = f"{key[:4]}.{key[4:6]}" if re.fullmatch(r"\d{6}", key) else key
        return ttl + ("(E)" if str(t.get("isConsensus", "N")).upper() == "Y" else "")

    rows = {}
    for r in (fi.get("rowList") or []):
        if not isinstance(r, dict): continue
        ttl = _clean_title(r.get("title", ""))
        cols = r.get("columns")
        if ttl in ITEMS and isinstance(cols, dict):
            for k, v in cols.items():
                rows.setdefault(ttl, {})[label(k)] = v.get("value") if isinstance(v, dict) else v
    if not rows:
        top = list(j)[:8] if isinstance(j, dict) else type(j).__name__
        raise RuntimeError(f"annual 구조 미인식 top={top}")
    fin = pd.DataFrame.from_dict(rows, orient="index")
    return fin[sorted(fin.columns)]


def fetch_meta(code):
    """종목명·현재가·시가총액(억)·업종 — 실패해도 None으로 진행"""
    name = price = mcap = sec = None
    try:
        b = _api_json(M_BASIC, code)
        for node in _walk(b):
            if isinstance(node, dict):
                name = name or node.get("stockName") or node.get("itemName")
                if price is None:
                    for k in ("closePrice", "currentPrice", "now", "nv"):
                        if node.get(k) not in (None, ""):
                            price = to_num(node[k]); break
    except Exception as e:
        print(f"  [debug] basic 실패 {code}: {e}")
    try:
        it = _api_json(M_INTEG, code)
        kv = {}
        for node in _walk(it):
            if isinstance(node, dict):
                key, val = node.get("code") or node.get("key"), node.get("value")
                if key and val is not None and not isinstance(val, (dict, list)):
                    kv[str(key)] = str(val)
                name = name or node.get("stockName") or node.get("itemName")
                if sec is None:
                    for k in ("industryGroupKor", "industryName", "upjongName", "sectorName"):
                        if node.get(k): sec = str(node[k]); break
        raw = (kv.get("marketValue") or kv.get("시총") or kv.get("시가총액") or "").replace(" ", "")
        m = re.search(r"(?:([\d,]+)조)?([\d,]+)?억?", raw)
        if m and (m.group(1) or m.group(2)):
            mcap = (to_num(m.group(1)) or 0) * 10000 + (to_num(m.group(2)) or 0)
        if price is None and kv.get("closePrice"): price = to_num(kv["closePrice"])
    except Exception as e:
        print(f"  [debug] integration 실패 {code}: {e}")
    return name, price, mcap, sec


# ───────────────────────── 지표 계산
def compute_stock(code: str) -> dict:
    fin = fetch_finance(code)
    name, price, mcap, naver_sec = fetch_meta(code)
    base = {"종목코드": code, "기업": name or "?", "현재가": price, "시총(억)": mcap, "네이버업종": naver_sec or ""}

    years = [c for c in fin.columns if re.fullmatch(r"\d{4}\.\d{2}(\(E\))?", c)]
    est = [y for y in years if "(E)" in y]
    act = [y for y in years if "(E)" not in y]
    if not est or not act:
        return {**base, "비고": "컨센서스 없음 → 산출불가"}

    def g(row, col):
        return to_num(fin.loc[row, col]) if row in fin.index and col in fin.columns else None

    y0 = est[0]
    rev0, op0 = g("매출액", y0), g("영업이익", y0)
    ni0, ni_note = g("지배주주순이익", y0), ""
    if ni0 is None:                                   # 지배주주 컨센 없으면 당기순이익으로 대체
        ni0, ni_note = g("당기순이익", y0), "순이익=당기순이익 대체;"
    hist = {n: (g("매출액", act[-n]), g("영업이익", act[-n])) for n in (1, 2, 3) if len(act) >= n}
    rev_1, op_1 = hist.get(1, (None, None))

    fper_site = g("PER", y0)
    mcap_note = ""
    if not mcap and fper_site and ni0 and ni0 > 0:      # 시총 못 읽으면 네이버 PER(E)로 역산(예외)
        mcap, mcap_note = fper_site * ni0, "시총역산;"
    fpor = mcap / op0 if mcap and op0 and op0 > 0 else None
    fper = mcap / ni0 if mcap and ni0 and ni0 > 0 else None
    opm0 = op0 / rev0 * 100 if op0 is not None and rev0 else None
    opm_1 = op_1 / rev_1 * 100 if op_1 is not None and rev_1 else None
    base_effect = op_1 is None or op_1 <= 0 or (opm_1 is not None and opm_1 < 3)

    pegs = {f"PEG({k}){n}y": None for n in (1, 2, 3) for k in ("매출", "영익")}
    for n, (r, o) in hist.items():
        pegs[f"PEG(매출){n}y"] = peg(fper, cagr(rev0, r, n))
        pegs[f"PEG(영익){n}y"] = peg(fper, cagr(op0, o, n))
    if base_effect:
        pegs["PEG(영익)1y"] = None

    dps = g("주당배당금", act[-1])
    return {**base, "순이익(E)": ni0, "당기순이익(E)": g("당기순이익", y0), "영업이익(E)": op0,
            "fPOR": fpor, "fPER": fper, "fPER(사이트)": fper_site, **pegs,
            "영업이익률(E)": opm0, "ROE(E)": g("ROE", y0), "부채비율": g("부채비율", act[-1]),
            "매출증가율1y": cagr(rev0, rev_1, 1), "영익증가율1y": cagr(op0, op_1, 1),
            "배당수익률": (dps / price * 100 if dps and price else None),
            "추정연도": y0, "전년영업이익률": opm_1, "전년도": act[-1],
            "비고": mcap_note + ni_note + ("기저효과→PEG(영익)1y 산출불가" if base_effect else "")}


# ───────────────────────── 스크리닝 (단일 기준 6개, 전부 충족 = 통과)
CRITERIA = {"PEG(매출)1y": 1.0, "PEG(영익)": 1.0, "ROE(E)": 10.0, "영업이익률(E)": 10.0, "fPER": 30.0, "전년영업이익률": 5.0}
BASE_GROWTH_CAP = 150.0      # 영익증가율 150% 초과 시 기저효과로 간주


def _ok(x, lo=None, hi=None):
    if x is None or x != x:
        return False
    return (lo is None or x >= lo) and (hi is None or x <= hi)


def screen(d: dict, sector1: str) -> dict:
    g = d.get
    flags, fail = [], []
    peg1, peg2, pegs1 = g("PEG(영익)1y"), g("PEG(영익)2y"), g("PEG(매출)1y")
    base = "기저효과" in (g("비고") or "") or _ok(g("영익증가율1y"), lo=BASE_GROWTH_CAP)
    if base:
        flags.append("기저효과")
    eff = peg2 if base else peg1                 # 유효 PEG(영익): 기저효과면 2y CAGR 기준
    d["유효PEG"] = eff
    fper, fsite, roe, opm = g("fPER"), g("fPER(사이트)"), g("ROE(E)"), g("영업이익률(E)")
    if fper and fsite and fsite > 0 and abs(fper / fsite - 1) > 0.3:
        flags.append("PER괴리")              # 지배주주 기준으로도 사이트 PER와 30%↑ 차이 → 우선주·자사주 영향

    if sector1 == "금융":
        d.update(Type="금융", 탈락조건="영업이익·PEG 기준 부적합(별도 판단)", 플래그=",".join(flags)); return d
    if fper is None and g("순이익(E)") is None:
        d.update(Type="보류", 탈락조건="컨센서스 없음", 플래그=",".join(flags)); return d

    if not _ok(pegs1, hi=CRITERIA["PEG(매출)1y"]): fail.append("PEG매출>1")
    if not _ok(eff, hi=CRITERIA["PEG(영익)"]): fail.append("PEG영익>1")
    if not _ok(roe, lo=CRITERIA["ROE(E)"]): fail.append("ROE<10")
    if not _ok(opm, lo=CRITERIA["영업이익률(E)"]): fail.append("이익률<10")
    if not _ok(fper, lo=0, hi=CRITERIA["fPER"]): fail.append("fPER>30")
    if not _ok(g("전년영업이익률"), lo=CRITERIA["전년영업이익률"]): fail.append("전년이익률<5")
    d.update(Type="통과" if not fail else "탈락", 탈락조건=",".join(fail), 플래그=",".join(flags))
    return d
