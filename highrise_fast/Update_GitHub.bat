cd /d "%TEMP%"
rmdir /s /q hbp_push 2>nul
git clone https://github.com/Tenslaster/highrise-bot-python.git hbp_push
cd hbp_push
rmdir /s /q highrise_fast
mkdir highrise_fast
robocopy "C:\Users\cedri\OneDrive\Bureau\RADIOS\HIGHRISE_SDK" highrise_fast /E /XD .git
git add -A
git commit -m "Update highrise_fast"
git push origin main
cd ..
rmdir /s /q hbp_push