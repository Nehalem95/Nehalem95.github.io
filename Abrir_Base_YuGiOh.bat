@echo off
cd /d "%~dp0"
start "YuGiOhBase" http://127.0.0.1:8765/index.html
python server.py
if errorlevel 1 (
  echo.
  echo No se pudo iniciar con python. Verifica que Python este instalado.
  pause
)
