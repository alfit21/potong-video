@echo off
chcp 65001 >nul
title Pemotong Video 9:16
cd /d "%~dp0"

echo ============================================
echo   Pemotong Video 9:16 - Persiapan Awal
echo ============================================
echo.

where ffmpeg >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] FFmpeg tidak ditemukan.
    echo.
    echo FFmpeg dibutuhkan untuk memproses video.
    echo Cara install:
    echo   1. Download dari https://www.gyan.dev/ffmpeg/builds/
    echo      pilih file "ffmpeg-release-full.7z".
    echo   2. Ekstrak, lalu tambahkan folder "bin" ke PATH Windows.
    echo      (Cara cepat: copy file ffmpeg.exe, ffprobe.exe ke C:\Windows\)
    echo   3. Buka lagi file run.bat ini.
    echo.
    pause
    exit /b 1
)

where ffprobe >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] ffprobe tidak ditemukan, padahal ffmpeg ada.
    echo Pastikan ffprobe.exe juga ada di PATH, lalu ulangi.
    pause
    exit /b 1
)

python -c "import flask" >nul 2>nul
if %errorlevel% neq 0 (
    echo Flask belum terinstall. Memasang Flask...
    pip install flask
    if %errorlevel% neq 0 (
        echo [ERROR] Gagal menginstall Flask. Coba jalankan: pip install flask
        pause
        exit /b 1
    )
)

echo Memulai aplikasi... Browser akan terbuka otomatis.
echo Tutup jendela ini untuk menghentikan server.
echo.
python app.py
pause