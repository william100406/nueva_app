@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set DATABASE_URL=sqlite:///facturacion.db
python app.py
pause
