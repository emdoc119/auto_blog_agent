#!/bin/bash

echo "=========================================="
echo "좀비 PC (MacBook Air 2011) 블로그 에이전트 셋업"
echo "=========================================="

echo "[1/4] 파이썬 가상환경(venv) 생성 중..."
python3 -m venv venv
source venv/bin/activate

echo "[2/4] 필요 패키지 설치 중..."
pip install -r requirements.txt

echo "[3/4] Playwright 브라우저 설치 중..."
playwright install chromium

echo "[4/4] 셋업 완료!"
echo ""
echo "이제 서버를 실행합니다..."
python app.py
