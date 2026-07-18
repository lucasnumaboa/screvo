@echo off
title Screvo - Build + Installer
color 0D
echo.
echo  ============================================
echo   Screvo - Build Completo
echo  ============================================
echo.

:: PASSO 1: Compila o EXE
echo  [1/2] Compilando aplicativo...
call build.bat
if errorlevel 1 (
    echo  [ERRO] Falha no build.
    pause
    exit /b 1
)

:: PASSO 2: Compila o instalador
echo.
echo  [2/2] Criando instalador com Inno Setup...

:: Procura Inno Setup
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else (
    echo  [AVISO] Inno Setup nao encontrado.
    echo  Instale de: https://jrsoftware.org/isdl.php
    echo  Depois abra installer.iss no Inno Setup e compile.
    pause
    exit /b 0
)

"%ISCC%" installer.iss
if errorlevel 1 (
    echo  [ERRO] Falha ao criar instalador.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   Tudo pronto!
echo   Instalador em: installer_output\
echo  ============================================
echo.
pause
