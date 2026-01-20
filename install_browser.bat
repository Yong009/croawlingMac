@echo off
chcp 65001
echo ========================================================
echo   Worknet Crawler 초기 설정 도구
echo ========================================================
echo.
echo 이 프로그램 실행에 필요한 '자동화 전용 브라우저'를 설치합니다.
echo 처음 한 번만 실행해주시면 됩니다.
echo.
echo [설치 시작] 인터넷 연결이 필요합니다...
echo.

python -m pip install playwright 2>nul
if %errorlevel% neq 0 (
    echo [알림] Python이 설치되어 있지 않거나 pip 명령어를 찾을 수 없습니다.
    echo 이 컴퓨터에 Python이 없다면, 아래의 '플레이라이트'만 따로 설치를 시도합니다.
)

echo.
echo 1. Playwright 브라우저 다운로드 중...
"dist\WorknetCrawlerGUI.exe" install-deps 2>nul
if %errorlevel% neq 0 (
    echo [시도 2] 기본 명령어로 설치 시도...
    playwright install chromium
)

echo.
echo ========================================================
echo   설치 과정이 완료되었습니다.
echo   이제 'WorknetCrawlerGUI.exe'를 실행하시면 됩니다!
echo ========================================================
pause
