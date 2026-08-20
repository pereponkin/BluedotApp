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

[Code]
var
  DeleteUserData: Boolean;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    DeleteUserData := False;
    if (not UninstallSilent) and
       DirExists(ExpandConstant('{localappdata}\BlueDotAgent')) then
    begin
      DeleteUserData :=
        MsgBox(
          'Удалить также все пользовательские данные Blue Dot Agent?' #13#10#13#10 +
          'Будут безвозвратно удалены настройки, API-ключи, история, ' +
          'браузерные профили и загруженный Playwright Firefox.' #13#10#13#10 +
          'Выберите «Нет», чтобы сохранить их для переустановки.',
          mbConfirmation,
          MB_YESNO or MB_DEFBUTTON2) = IDYES;
    end;
  end
  else if (CurUninstallStep = usPostUninstall) and DeleteUserData then
  begin
    if (not DelTree(
      ExpandConstant('{localappdata}\BlueDotAgent'), True, True, True)) and
      (not UninstallSilent) then
    begin
      MsgBox(
        'Не удалось полностью удалить пользовательские данные из:' #13#10 +
        ExpandConstant('{localappdata}\BlueDotAgent') + #13#10#13#10 +
        'Закройте браузер агента и удалите эту папку вручную.',
        mbError,
        MB_OK);
    end;
  end;
end;
