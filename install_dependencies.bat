@echo off
echo Starting dependency installation...

pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo Dependencies installed successfully!
) else (
    echo Error installing dependencies. Please check the output above.
)

pause