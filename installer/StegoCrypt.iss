#define MyAppName "StegoCrypt"
#ifndef MyAppVersion
  ; Fallback for local/manual builds; CI will override via /DMyAppVersion=<tag>
  #define MyAppVersion "0.0.0"
#endif
#define MyAppPublisher "Your Name or Org"
#define MyAppExeName "StegoCrypt.exe"

[Setup]
AppId={{B5E9F2C6-1B4A-4A6B-B3C6-ABCDEF123456}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=Output
DisableProgramGroupPage=yes
OutputBaseFilename=Windows-StegoCrypt-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\StegoCrypt\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent




