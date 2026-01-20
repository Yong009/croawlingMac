@echo off
chcp 65001
echo GUI 버전 빌드 시작 (WorknetCrawlerGUI) ...
echo.

echo 1. 기존 빌드 정리
rmdir /s /q build dist 2>nul
del *.spec 2>nul

echo 2. PyInstaller 실행 (GUI 모드)
echo 잠시만 기다려주세요...
python -m PyInstaller --noconfirm --onefile --noconsole --name "WorknetCrawlerGUI" --clean --collect-all playwright --hidden-import=openpyxl worknet_crawler_gui.py

echo.
if exist "dist\WorknetCrawlerGUI.exe" (
    echo [성공] 실행 파일 생성 완료!
    echo 경로: dist\WorknetCrawlerGUI.exe
    echo.
    echo 바로 실행해봅니다...
    start dist\WorknetCrawlerGUI.exe
) else (
    echo [실패] 파일을 만들지 못했습니다.
)
pause
