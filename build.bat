@echo off
setlocal
cd /d "%~dp0"
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
if not exist build mkdir build
cl /nologo /std:c++17 /O2 /EHsc /W3 /utf-8 src\main.cpp /Fo:build\ /Fe:DFRecoil.exe /link /SUBSYSTEM:WINDOWS
if errorlevel 1 (echo BUILD FAILED & exit /b 1)
echo BUILD OK
