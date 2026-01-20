@echo off
cd /d c:\worknetCrawlling

echo [1/6] 기존 설정 및 캐시 정리 중...
rmdir /s /q .git 2>nul
rem 이미 생성된 무거운 빌드 폴더는 업로드하지 않습니다.
rem .gitignore 파일이 적용될 것입니다.

echo [2/6] Git 저장소 다시 생성 중...
git init
git branch -m main

echo [3/6] 소스 코드만 담는 중 (실행 파일 제외)...
git add .

echo [4/6] 기록 남기는 중...
git commit -m "Clean source upload"

echo [5/6] GitHub 연결 중...
git remote add origin https://github.com/Yong009/croawlingMac.git

echo [6/6] 업로드 시작 (재시도)...
git push -u origin main --force

echo.
echo === 완료되었습니다. GitHub Actions 탭을 확인하세요. ===
pause
