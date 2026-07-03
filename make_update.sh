#!/bin/bash

echo "=========================================="
echo "좀비 PC용 업데이트 패치 생성기"
echo "=========================================="

cd /Users/choo/.gemini/antigravity/scratch/blog_agent

# DB파일, 쿠키파일, 가상환경 등을 제외하고 순수 코드만 압축
zip -r ../blog_agent_update.zip . -x "*.db" -x "*.json" -x "venv/*" -x "*/__pycache__/*" -x "*.DS_Store"

echo "=========================================="
echo "✅ 업데이트 파일(blog_agent_update.zip)이 생성되었습니다!"
echo "이 파일을 구형 맥북으로 보내서 기존 폴더에 '덮어쓰기' 하시면 됩니다."
