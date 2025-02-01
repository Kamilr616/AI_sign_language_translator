@echo off

REM Change directory
cd .\src

REM Activate the virtual environment
call ..\venv\Scripts\activate.bat

REM Run the Python script
python .\main.py
