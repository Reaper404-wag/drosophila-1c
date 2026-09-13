@echo off
chcp 65001 > nul
cd /d "%~dp0"
title Муха и 1С
echo.
echo   Муха закрывает лабораторные по 1С
echo   --------------------------------
echo.
echo   [1] Открыть стартовую страницу (всё сразу)
echo   [2] Сцена: муха делает лабораторную
echo   [3] Лаборатория коннектома
echo   [4] Отчёт по 12 лабораторным
echo   [5] Проверить платформу 1С
echo   [6] Пересобрать всё заново (долго)
echo   [0] Выход
echo.
set /p choice="  Что открываем? "

if "%choice%"=="1" goto home
if "%choice%"=="2" start "" "report\stage.html" & goto end
if "%choice%"=="3" start "" "report\lab.html" & goto end
if "%choice%"=="4" start "" "report\index.html" & goto end
if "%choice%"=="5" goto platform
if "%choice%"=="6" goto rebuild
goto end

:home
python -c "from fly1c import viz_home; print(viz_home.build())" > nul 2>&1
start "" "report\home.html"
goto end

:platform
python run_lab.py platform
echo.
pause
goto end

:rebuild
echo.
echo   Пересобираю: прогон мухи по всем лабораторным, отчёт, сцена, лаборатория.
echo   Это занимает около 20 минут.
echo.
python run_lab.py report
python run_lab.py stage
python run_lab.py lab
python -c "from fly1c import viz_home; print(viz_home.build())"
echo.
echo   Готово. Открываю стартовую страницу.
start "" "report\home.html"
pause
goto end

:end
