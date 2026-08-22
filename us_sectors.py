"""미국 종목 섹터: StockAnalysis 'Industry' 문자열 키워드 → 1차 섹터. 수동 오버라이드 우선."""
MANUAL = {
    "NVDA": "반도체", "AMD": "반도체", "INTC": "반도체", "TSM": "반도체", "ASML": "반도체", "ARM": "반도체", "QCOM": "반도체",
    "AVGO": "반도체", "MU": "반도체", "TSEM": "반도체", "SKHY": "반도체", "SNDK": "반도체", "WDC": "반도체", "STX": "반도체",
    "AAOI": "AI·전력인프라", "LITE": "AI·전력인프라", "DELL": "AI·전력인프라", "VRT": "AI·전력인프라",
    "GOOG": "인터넷·플랫폼", "GOOGL": "인터넷·플랫폼", "AMZN": "인터넷·플랫폼", "META": "인터넷·플랫폼", "BABA": "인터넷·플랫폼",
    "PDD": "인터넷·플랫폼", "MELI": "인터넷·플랫폼", "EBAY": "인터넷·플랫폼",
    "MSFT": "소프트웨어", "CRM": "소프트웨어", "NOW": "소프트웨어", "SAP": "소프트웨어", "SNOW": "소프트웨어", "IBM": "소프트웨어",
    "ACN": "소프트웨어", "ROP": "소프트웨어", "ORCL": "소프트웨어", "PLTR": "소프트웨어",
    "COIN": "금융", "MSTR": "금융",
}
KEYWORDS = [
    ("Semiconductor", "반도체"), ("Computer Hardware", "AI·전력인프라"), ("Communication Equipment", "AI·전력인프라"),
    ("Electrical", "AI·전력인프라"), ("Electronic Components", "AI·전력인프라"), ("Scientific", "AI·전력인프라"),
    ("Software", "소프트웨어"), ("Information Technology Services", "소프트웨어"), ("IT Services", "소프트웨어"),
    ("Internet", "인터넷·플랫폼"), ("Interactive Media", "인터넷·플랫폼"), ("Retail", "인터넷·플랫폼"), ("Advertising", "인터넷·플랫폼"),
    ("Biotech", "바이오·헬스케어"), ("Drug", "바이오·헬스케어"), ("Pharma", "바이오·헬스케어"), ("Medical", "바이오·헬스케어"),
    ("Health", "바이오·헬스케어"), ("Diagnostics", "바이오·헬스케어"),
    ("Aerospace", "우주·방산"), ("Defense", "우주·방산"),
    ("Auto", "자동차·모빌리티"), ("Bank", "금융"), ("Capital Markets", "금융"), ("Insurance", "금융"), ("Financial", "금융"),
    ("Asset Management", "금융"), ("Credit", "금융"),
    ("Oil", "에너지"), ("Gas", "에너지"), ("Solar", "에너지"), ("Utilities", "에너지"), ("Uranium", "에너지"),
    ("Restaurant", "소비재"), ("Beverage", "소비재"), ("Apparel", "소비재"), ("Footwear", "소비재"), ("Household", "소비재"),
    ("Luxury", "소비재"), ("Leisure", "소비재"), ("Travel", "소비재"), ("Lodging", "소비재"), ("Personal", "소비재"), ("Food", "소비재"),
    ("Entertainment", "엔터·미디어"), ("Media", "엔터·미디어"), ("Gaming", "엔터·미디어"), ("Telecom", "엔터·미디어"),
    ("Industrial", "산업재"), ("Machinery", "산업재"), ("Building", "산업재"), ("Construction", "산업재"), ("Engineering", "산업재"),
    ("Steel", "소재"), ("Chemical", "소재"), ("Metal", "소재"), ("Mining", "소재"), ("Gold", "소재"), ("Copper", "소재"),
    ("Real Estate", "부동산"), ("REIT", "부동산"),
]
ORDER = ["반도체", "AI·전력인프라", "소프트웨어", "인터넷·플랫폼", "바이오·헬스케어", "우주·방산", "자동차·모빌리티",
         "에너지", "소비재", "엔터·미디어", "산업재", "소재", "금융", "부동산", "미분류"]


def classify(ticker: str, industry: str | None):
    if ticker in MANUAL:
        return MANUAL[ticker], industry or ""
    ind = industry or ""
    for kw, sec in KEYWORDS:
        if kw.lower() in ind.lower():
            return sec, ind
    return "미분류", ind
