@echo off
setlocal
set PROGRAM=%0
cd /d "%~dp0"
python "download.py" %*
