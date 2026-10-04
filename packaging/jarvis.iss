#define MyAppName "J.A.R.V.I.S."
#define MyAppVersion "0.3.0"
#define MyAppPublisher "H@CKERBOY"
#define MyAppExeName "JARVIS.exe"

[Setup]
AppId={{D80A2C9E-62EF-4C6D-A2A3-5ED2EC13E9B1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName=J.A.R.V.I.S.
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=JARVIS-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=no
CloseApplications=yes
RestartApplications=no

[Files]
Source: "..\dist\J.A.R.V.I.S\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\J.A.R.V.I.S."; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\J.A.R.V.I.S."; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Lancer J.A.R.V.I.S."; Flags: nowait postinstall skipifsilent
