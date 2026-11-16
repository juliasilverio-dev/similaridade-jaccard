@echo off
setlocal
cd /d "%~dp0backend"
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo Criando o ambiente Python...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

.venv\Scripts\python.exe -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Instalando as dependencias...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)

echo Abra http://127.0.0.1:5000 no navegador. Para encerrar, pressione Ctrl+C.
.venv\Scripts\python.exe run.py
exit /b %errorlevel%
