@echo off
cd /d %~dp0
python start_daemon.py --force %*
pause
