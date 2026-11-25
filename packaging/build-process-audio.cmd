@echo off
setlocal
for /f "usebackq delims=" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "AEGIS_VS=%%i"
if not defined AEGIS_VS (
    echo Visual Studio C++ Build Tools with a Windows 11 SDK are required for process audio. 1>&2
    exit /b 1
)
call "%AEGIS_VS%\Common7\Tools\VsDevCmd.bat" -no_logo -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 1
if not exist "%~dp0vendor" mkdir "%~dp0vendor"
cl /nologo /std:c++17 /W4 /WX /EHsc /O2 /MT /D_WIN32_WINNT=0x0A00 "%~dp0process_audio.cpp" /Fo"%~dp0vendor\process_audio.obj" /Fe"%~dp0vendor\aegis-process-audio.exe" /link Ole32.lib Mmdevapi.lib
exit /b %errorlevel%
