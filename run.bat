@echo off
if "%1"=="test" (
    set COVERAGE_CORE=pytrace
    python -m coverage run --branch --source=src -m unittest discover -s tests
    if errorlevel 1 exit /b 1
    python -m coverage report -m
    if errorlevel 1 exit /b 1
    python -m pycodestyle src tests
    exit /b
)
python src/main.py %1
