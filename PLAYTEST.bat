@echo off
setlocal
title Silo 81 - Playtest
set "GODOT=D:\Godot4.3\Godot_v4.3-stable_win64.exe"
set "GAME=D:\Silo-81-main\Silo-81-main\game"

if not exist "%GODOT%" (
  echo Godot was not found at %GODOT%
  echo Edit PLAYTEST.bat and set GODOT to your Godot 4.3 executable.
  pause
  exit /b 1
)

:menu
cls
echo ============================================================
echo   SILO 81 - PLAYTEST
echo ============================================================
echo   1. Full game (intro on Level 2)
echo   2. Level 3 - pipe gallery (worms / combat)
echo   3. Level 4 - Command
echo   4. Heating Control Room (L4E)
echo   5. Sub-Level 4 - Geotherm / Deep Storage (L5)
echo   6. Level 1 - Surface Transit Depot
echo   7. Junk Town - gate yard
echo   8. Junk Town - animal pen
echo   9. Junk Town - god mode
echo  10. Level 2 West - commons / kitchen / clinic
echo  11. Administration Office (Overseer)
echo   0. Run autotest (headless)
echo   Q. Quit
echo ============================================================
set /p pick=Choose: 

if /i "%pick%"=="1" ( start "" "%GODOT%" --path "%GAME%" & goto menu )
if /i "%pick%"=="2" ( start "" "%GODOT%" --path "%GAME%" -- --start=L3,6.6,-0.2 & goto menu )
if /i "%pick%"=="3" ( start "" "%GODOT%" --path "%GAME%" -- --start=L4W & goto menu )
if /i "%pick%"=="4" ( start "" "%GODOT%" --path "%GAME%" -- --start=L4E & goto menu )
if /i "%pick%"=="5" ( start "" "%GODOT%" --path "%GAME%" -- --start=L5 & goto menu )
if /i "%pick%"=="6" ( start "" "%GODOT%" --path "%GAME%" -- --start=L1 & goto menu )
if /i "%pick%"=="7" ( start "" "%GODOT%" --path "%GAME%" -- --start=JT,12,0 & goto menu )
if /i "%pick%"=="8" ( start "" "%GODOT%" --path "%GAME%" -- --start=JT,19,-4 & goto menu )
if /i "%pick%"=="9" ( start "" "%GODOT%" --path "%GAME%" -- --start=JT,12,0 --god & goto menu )
if /i "%pick%"=="10" ( start "" "%GODOT%" --path "%GAME%" -- --start=L2W & goto menu )
if /i "%pick%"=="11" ( start "" "%GODOT%" --path "%GAME%" -- --start=L4W,-27.8,7.2 & goto menu )
if /i "%pick%"=="0" (
  "%GODOT%" --headless --fixed-fps 60 --path "%GAME%" -- --autotest
  echo.
  pause
  goto menu
)
if /i "%pick%"=="q" exit /b 0
goto menu

