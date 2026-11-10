; Local integration build. Proprietary data require local redistribution rights.
#ifndef BuildRoot
  #error BuildRoot must be supplied by build_clone_windows.py
#endif
#ifndef IncludeLocalData
  #define IncludeLocalData 0
#endif
#ifndef PayloadRoot
  #define PayloadRoot BuildRoot + "\WoWCartoForever-Client"
#endif
#ifndef ProductNumericVersion
  #define ProductNumericVersion "0.9.1"
#endif
#ifndef ProductVersion
  #define ProductVersion ProductNumericVersion
#endif
#define ProductName "WoWCarto Forever"
#define ProductExe "WoWCartoForever-Client.exe"

[Setup]
AppId={code:InstallationId}
AppName={#ProductName}
AppVersion={#ProductNumericVersion}
AppVerName={#ProductName} {#ProductVersion}
AppPublisher=WoWCarto Forever
DefaultDirName={code:DefaultInstallationDir}
DefaultGroupName={#ProductName}
DisableProgramGroupPage=yes
UsePreviousLanguage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#BuildRoot}\installer
OutputBaseFilename=WoWCartoForever-Setup
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
#ifdef AppIcon
SetupIconFile={#AppIcon}
#endif
CloseApplications=yes
CloseApplicationsFilter=WoWCartoForever-Client.exe
UninstallDisplayIcon={app}\{#ProductExe}
UninstallDisplayName={code:DisplayInstallationName}

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Messages]
fr.WelcomeLabel2=Ce programme installe {#ProductName} {#ProductVersion} pour votre compte Windows.%n%nVos annotations et sauvegardes personnelles restent séparées du programme et sont conservées lors des mises à jour et de la désinstallation.
en.WelcomeLabel2=This will install {#ProductName} {#ProductVersion} for your Windows account.%n%nYour personal annotations and backups remain separate from the program and are kept during updates and uninstallation.

[CustomMessages]
fr.DesktopShortcut=Créer un raccourci sur le Bureau
en.DesktopShortcut=Create a desktop shortcut
fr.ShortcutGroup=Raccourcis :
en.ShortcutGroup=Shortcuts:
fr.LaunchClient=Lancer WoWCarto Forever
en.LaunchClient=Launch WoWCarto Forever

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:ShortcutGroup}"; Check: IsNormalInstallation

[Files]
Source: "{#PayloadRoot}\*"; DestDir: "{app}"; Excludes: "data\*"; Flags: ignoreversion recursesubdirs createallsubdirs
#if IncludeLocalData
Source: "{#PayloadRoot}\data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif

[Icons]
Name: "{autoprograms}\{#ProductName}"; Filename: "{app}\{#ProductExe}"; Check: IsNormalInstallation
Name: "{autodesktop}\{#ProductName}"; Filename: "{app}\{#ProductExe}"; Tasks: desktopicon; Check: IsNormalInstallation
Name: "{autoprograms}\{#ProductName} - test"; Filename: "{app}\{#ProductExe}"; Parameters: "{code:LaunchParameters}"; Check: IsValidationSandbox

[Run]
Filename: "{app}\{#ProductExe}"; Parameters: "{code:LaunchParameters}"; Description: "{cm:LaunchClient}"; Flags: nowait postinstall skipifsilent

; Personal SQLite/preferences/cache files stay outside {app}. Never uninstall them.

[Code]
function IsValidationSandbox: Boolean;
begin
  Result := ExpandConstant('{param:ValidationSandbox|0}') = '1';
end;

function IsNormalInstallation: Boolean;
begin
  Result := not IsValidationSandbox;
end;

function DefaultInstallationDir(Param: String): String;
begin
  if IsValidationSandbox then
    Result := ExpandConstant('{localappdata}\Programs\WoWCartoForever-Test')
  else
    Result := ExpandConstant('{localappdata}\Programs\WoWCartoForever');
end;

function LaunchParameters(Param: String): String;
begin
  { Tests must never open or create the normal user's profile. }
  if IsValidationSandbox then
    Result := '--state "' + ExpandConstant('{localappdata}\WoWCartoForever-Test\annotations.sqlite3') + '"'
  else
    Result := '';
end;

function DisplayInstallationName(Param: String): String;
begin
  if IsValidationSandbox then
    Result := '{#ProductName} - test'
  else
    Result := '{#ProductName}';
end;

function InstallationId(Param: String): String;
begin
  { Explicit sandbox switch prevents acceptance installs from replacing the user's uninstall registration. }
  if IsValidationSandbox then
    Result := 'WoWCartoForever-Client-Test-091'
  else
    Result := '{AD301735-3239-4622-B485-02F379E6EE53}';
end;
