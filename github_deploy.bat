@echo off
chcp 65001
echo === GitHub 배포 및 Actions 트리거 ===
echo.

echo 1. 변경사항 스테이징 (git add)
git add .
echo.

echo 2. 커밋 생성 (git commit)
set /p commit_msg="커밋 메시지를 입력하세요 (엔터치면 기본값 사용): "
if "%commit_msg%"=="" set commit_msg=Update code and trigger build
git commit -m "%commit_msg%"
echo.

echo 3. GitHub로 푸시 (git push)
echo 원격 저장소: https://github.com/Yong009/croawlingMac.git
git push origin main

if %errorlevel% neq 0 (
    echo.
    echo [오류] 푸시에 실패했습니다. Remote 설정이 올바른지 확인하거나 push_to_github.bat를 먼저 실행해보세요.
    pause
    exit /b
)

echo.
echo [성공] 푸시가 완료되었습니다!
echo GitHub Actions 탭에서 빌드 진행 상황을 확인하세요.
echo https://github.com/Yong009/croawlingMac/actions
echo.
pause
