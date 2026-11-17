@echo off
rem Analiza tu ultima partida de Age of Empires II: DE y abre el informe.
rem Doble clic: la partida mas reciente. Arrastrar un .aoe2record encima: esa partida.
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONWARNINGS=ignore

rem 1. Buscar Python 3.11 o superior
set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo No encuentro Python 3.11 o superior.
  echo Instalalo desde la pagina que se va a abrir. Durante la instalacion marca
  echo la casilla "Add python.exe to PATH". Luego vuelve a hacer doble clic aqui.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

rem 2. Preparar el entorno la primera vez (tarda un minuto)
if not exist ".venv\listo.txt" (
  echo Preparando el entorno por primera vez...
  if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check "mgz==1.8.51" || goto :error
  echo ok> ".venv\listo.txt"
)

rem 3. Analizar
".venv\Scripts\python.exe" tools\lanzador.py %* || goto :error
echo.
pause
exit /b 0

:error
echo.
echo Algo ha fallado. Copia el texto de arriba y pasamelo.
pause
exit /b 1
