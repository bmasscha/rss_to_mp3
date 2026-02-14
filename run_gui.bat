@echo off
setlocal

:: Clear any existing Python/Conda/Qt environment variables that might interfere
set "PYTHONPATH="
set "PYTHONHOME="
set "CONDA_PREFIX="
set "CONDA_SHLVL="
set "CONDA_DEFAULT_ENV="
set "CONDA_PYTHON_EXE="
set "QT_PLUGIN_PATH="
set "QT_QPA_PLATFORM_PLUGIN_PATH="
set "QML2_IMPORT_PATH="

:: Set base directory
set "BASE_DIR=%~dp0"

:: Explicitly construct the path to the qt binaries in the venv
set "QT_BIN_DIR=%BASE_DIR%venv\Lib\site-packages\PyQt6\Qt6\bin"

:: Construct a minimal PATH
:: 1. venv Scripts (for python.exe)
:: 2. Qt6 bin (for DLLs)
:: 3. standard Windows paths
set "PATH=%BASE_DIR%venv\Scripts;%QT_BIN_DIR%;%SystemRoot%\system32;%SystemRoot%;%SystemRoot%\System32\Wbem"

echo ======================================================
echo Starting RSS to MP3 Gui (Isolated Environment)
echo ======================================================
echo Base Dir: %BASE_DIR%
echo Python:   %BASE_DIR%venv\Scripts\python.exe
echo Qt Bin:   %QT_BIN_DIR%
echo.

:: Run the script
python "%BASE_DIR%rss_to_mp3_gui.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] The application exited with error code %ERRORLEVEL%.
    echo Please check the output above.
    pause
)
endlocal
