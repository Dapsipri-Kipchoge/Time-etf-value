# TIME ETF 국내 보유종목 밸류 스크리너 (개인용)

구조: GitHub Actions(평일 18:30 KST)가 타임폴리오 국내 ETF 8종 구성종목 → FnGuide 컨센서스 수집 → `data/*.csv` 커밋 → Streamlit Cloud가 CSV를 읽어 표시.

## 배포 순서
1. 이 폴더를 GitHub 새 저장소(private 가능)에 push
2. Actions 탭 → `daily-collect` → Run workflow (첫 수집, 약 5~10분)
3. share.streamlit.io → New app → 저장소 선택, Main file `app.py` → Deploy
4. 이후 매 평일 자동 갱신. 앱 우측 "지금 새로고침" 버튼은 실시간 FnGuide 재호출(옵션)

## 로컬 테스트
```
pip install -r requirements.txt
python collect.py          # data/ 생성
streamlit run app.py
```
