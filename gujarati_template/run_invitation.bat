@echo off
REM Easy way to run the Gujarati invitation template

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Run the template renderer
echo Running Gujarati Invitation Renderer...
echo.

python render_json_template.py sample_gujarati_template.json --output ..\output\gujarati_invitation.png

echo.
echo Rendered invitation saved to: ..\output\gujarati_invitation.png
pause
