@echo off
title Screvo - Build
color 0D
echo.
echo  ============================================
echo   Screvo - Compilacao para EXE
echo  ============================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERRO] Python nao encontrado. Instale Python 3.10+
    pause
    exit /b 1
)

:: Instala dependencias
echo  [1/3] Instalando dependencias...
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERRO] Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo  [2/3] Compilando com PyInstaller...

:: Compila
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "Screvo" ^
    --icon "resources\icon.ico" ^
    --add-data "ffmpeg\bin\ffmpeg.exe;ffmpeg\bin" ^
    --add-data "ffmpeg\bin\ffprobe.exe;ffmpeg\bin" ^
    --hidden-import "screeninfo" ^
    --hidden-import "keyboard" ^
    --hidden-import "requests" ^
    --hidden-import "pyaudiowpatch" ^
    --hidden-import "sherpa_onnx" ^
    --hidden-import "numpy" ^
    --collect-all "sherpa_onnx" ^
    --collect-all "pyaudiowpatch" ^
    --collect-all "numpy" ^
    --hidden-import "PIL" ^
    --hidden-import "PyQt6.QtWidgets" ^
    --hidden-import "PyQt6.QtCore" ^
    --hidden-import "PyQt6.QtGui" ^
    --hidden-import "PyQt6.QtMultimedia" ^
    --hidden-import "PyQt6.QtMultimediaWidgets" ^
    main.py

if errorlevel 1 (
    echo.
    echo  [ERRO] Falha na compilacao.
    pause
    exit /b 1
)

echo.
echo  [3/3] Build concluido!
echo.
echo  Executavel em: dist\Screvo.exe
echo.

:: Copia FFmpeg para pasta dist
echo  Copiando FFmpeg para dist...
if not exist "dist\ffmpeg\bin" mkdir "dist\ffmpeg\bin"
copy "ffmpeg\bin\ffmpeg.exe" "dist\ffmpeg\bin\" >nul
copy "ffmpeg\bin\ffprobe.exe" "dist\ffmpeg\bin\" >nul

echo  FFmpeg copiado.
echo.
echo  ============================================
echo   Build finalizado com sucesso!
echo   Pasta de saida: dist\
echo  ============================================
echo.
pause
