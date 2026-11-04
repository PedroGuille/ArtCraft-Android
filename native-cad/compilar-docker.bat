@echo off
setlocal
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 (
  echo Instala e inicia Docker Desktop, con contenedores Linux.
  pause
  exit /b 1
)
set "SOURCE_ZIP=%~1"
if defined SOURCE_ZIP goto :have_zip
set "ZIP_COUNT=0"
for %%F in (*.zip) do call :found "%%F"
if not "%ZIP_COUNT%"=="1" goto :choose_zip
:have_zip
if not exist "%SOURCE_ZIP%" goto :choose_zip
for %%F in ("%SOURCE_ZIP%") do set "SOURCE_NAME=%%~nxF"
for %%F in ("%SOURCE_ZIP%") do set "SOURCE_DIR=%%~dpF"
if /I not "%SOURCE_DIR%"=="%~dp0" goto :choose_zip
docker build --platform linux/amd64 -t cadcraft-tablet-builder:1.0 .
if errorlevel 1 goto :failed
docker run --rm --platform linux/amd64 --mount "type=bind,src=%cd%,dst=/project" --mount type=volume,src=cadcraft-tablet-cargo-registry,dst=/opt/cadcraft-toolchain/cargo/registry --mount type=volume,src=cadcraft-tablet-cargo-git,dst=/opt/cadcraft-toolchain/cargo/git cadcraft-tablet-builder:1.0 build "/project/%SOURCE_NAME%" --output "/project/work/%SOURCE_NAME%" --artifacts /project/dist
if errorlevel 1 goto :failed
echo APK y simbolos disponibles en dist.
pause
exit /b 0
:found
set /a ZIP_COUNT+=1
set "SOURCE_ZIP=%~1"
exit /b
:choose_zip
echo Copia un solo ZIP original de CadCraft junto a este archivo y vuelve a abrirlo.
pause
exit /b 2
:failed
echo La compilacion se detuvo. Revisa el mensaje anterior y dist\build.log si existe.
pause
exit /b 1
