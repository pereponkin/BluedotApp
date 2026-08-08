#define MyAppName "Blue Dot Agent"
#define MyAppVersion GetEnv("BLUEDOT_VERSION")
#define MyAppExeName "BlueDotAgent.exe"
#define PayloadDir GetEnv("BLUEDOT_PAYLOAD_DIR")
#define OutputDir GetEnv("BLUEDOT_INSTALLER_OUTPUT")

[Setup]
AppId={{8831E43D-7366-4D6A-BF25-F4D11389DF90}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\BlueDotAgent
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=BlueDotAgent-Setup-Windows-x64
SetupIconFile=..\BlueDotAgent.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
