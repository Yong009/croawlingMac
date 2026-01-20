@echo off
cd /d c:\worknetCrawlling
rmdir /s /q .git
git init
git branch -m main
git add .
git commit -m "Fix macOS runner and add deployment target for compatibility"
git remote add origin https://github.com/Yong009/croawlingMac.git
git push -u origin main --force
echo Done.
