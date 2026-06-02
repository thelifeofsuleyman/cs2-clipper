; Inno Setup script for Aegis Clipper.
;
; Wraps the PyInstaller output (dist\AegisClipper) into one signed-able installer
; exe. Produces a Start-menu shortcut, an optional desktop icon, an optional
; "launch at Windows startup" task, and launches the app (which opens the setup
; wizard in the browser on first run).
;
; Build:
;   1. pyinstaller packaging\aegis.spec        (from repo root)
;   2. open this file in Inno Setup Compiler (or: iscc packaging\aegis.iss)
; Output: packaging\Output\AegisClipper-Setup.exe

#define AppName "Aegis Clipper"
; Version is single-sourced from aegis/__init__.py; build.ps1 passes it via
; /DAppVersion=x.y.z. The fallback here keeps a manual `iscc aegis.iss` working.
#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif
#define AppExe "AegisClipper.exe"

[Setup]
AppId={{A3G15C71-CL1P-4PER-CS22-AEG1SCLIPPER}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Aegis Clipper
DefaultDirName={autopf}\AegisClipper
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=AegisClipper-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Per-user install needs no admin; flip to admin if installing to Program Files.
PrivilegesRequiredOverridesAllowed=dialog
; ── in-place upgrade support ──
; Stamp the binary so the in-app updater and Windows see the new version.
VersionInfoVersion={#AppVersion}
UninstallDisplayName={#AppName}
; Use the Restart Manager to close a running AegisClipper.exe during a /SILENT
; update and relaunch it afterwards, so files can be swapped without a reboot.
CloseApplications=yes
RestartApplications=yes
; A stable AppId (above) means a re-run upgrades the existing install in place,
; keeping the install dir; all user state lives in %APPDATA% and is never touched.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start {#AppName} automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Bundle the entire PyInstaller dist folder.
Source: "..\dist\AegisClipper\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
; "startup" task: a shortcut in the user's Startup folder.
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
