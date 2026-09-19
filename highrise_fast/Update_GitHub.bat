@echo off

set "SOURCE=C:\Users\cedri\OneDrive\Bureau\RADIOS\HIGHRISE_SDK"

cd /d "%TEMP%"
rmdir /s /q hbp_push 2>nul

git clone https://github.com/Tenslaster/highrise-bot-python.git hbp_push
cd hbp_push

if exist highrise_fast rmdir /s /q highrise_fast
mkdir highrise_fast

robocopy "%SOURCE%" highrise_fast /E /XD .git __pycache__ /XF *.pyc

git add -A
git diff --cached --quiet || git commit -m "Delete and recreate highrise_fast"
git push origin main

cd ..
rmdir /s /q hbp_push

echo Done.
pause