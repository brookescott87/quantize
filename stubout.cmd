@echo off

for %%f in (%*) do (
    if exist "%%~f" goto confirm
)
goto proceed

:confirm
echo To be deleted:
for %%f in (%*) do (
    echo.    %%~f
)
choice /c YN /m "Proceed"
if errorlevel 2 goto :abort
if errorlevel 1 goto :proceed
echo *Cancel*

:abort
echo Not confirmed.
goto :eof

:proceed
for %%f in (%*) do (
    if exist "%%~f" del /f "%%~f"
    mklink "%%~f" nul
)
