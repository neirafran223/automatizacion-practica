@echo off
chcp 65001 >nul
title Planillas ML - Generador web
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto :sinpython
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 goto :pythonviejo

if exist "venv\Scripts\python.exe" goto :listo
echo.
echo  Creando el entorno virtual (solo la primera vez)...
python -m venv venv
if errorlevel 1 goto :error

:listo
venv\Scripts\python.exe -c "import flask, openpyxl, requests" >nul 2>nul
if errorlevel 1 goto :instalar
goto :correr

:instalar
echo.
echo  Instalando flask, openpyxl, requests, beautifulsoup4 y pillow (solo la primera vez)...
venv\Scripts\python.exe -m pip install --disable-pip-version-check -q flask openpyxl requests beautifulsoup4 pillow
if errorlevel 1 goto :error

:correr
echo.
echo  Abriendo http://127.0.0.1:8778 ...
echo  (deja esta ventana abierta; para cerrar: X)
start "" http://127.0.0.1:8778
"%~dp0venv\Scripts\python.exe" -m webapp.app
pause
exit /b 0

:sinpython
echo.
echo  No encontre Python. Instalalo desde https://www.python.org/downloads/
echo  y MARCA "Add Python to PATH".
pause
exit /b 1

:pythonviejo
echo.
echo  Tu Python es anterior a 3.9. Instala una version mas nueva.
pause
exit /b 1

:error
echo.
echo  Algo fallo al preparar la app. Revisa tu conexion la primera vez.
pause
exit /b 1
