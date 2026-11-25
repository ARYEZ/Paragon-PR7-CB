; Paragon PR7-CB installer (Inno Setup 6): clipboard history, the way Ditto keeps it.
;   iscc /DAppVersion=0.1.0 installer\pr7cb.iss      (after pyinstaller pr7cb.spec has made dist\PR7-CB)
;
; Per-user (no admin rights) into %LOCALAPPDATA%\Programs\PR7-CB, with a Start menu entry. Ticked by default, PR7-CB
; starts with Windows (an HKCU Run entry written by PR7-CB itself: --startup on|off, so installer and Options agree):
; a clipboard history only remembers while it runs. --unregister on uninstall takes the entry away.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId is permanent: it's how a new version finds and upgrades the installed one. Never change it.
AppId={{5F4E0C50-1C11-4E53-A835-221E3BBB7509}
AppName=Paragon PR7-CB
AppVersion={#AppVersion}
AppVerName=Paragon PR7-CB {#AppVersion}
AppPublisher=Paragon
VersionInfoVersion={#AppVersion}
PrivilegesRequired=lowest
DefaultDirName={autopf}\PR7-CB
DefaultGroupName=Paragon PR7-CB
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
UsePreviousTasks=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist
OutputBaseFilename=PR7-CB-Setup-{#AppVersion}
SetupIconFile=..\pr7cb\icons\app.ico
UninstallDisplayIcon={app}\PR7-CB.exe
UninstallDisplayName=Paragon PR7-CB
WizardStyle=modern
WizardImageFile=wizard-large-1x.bmp,wizard-large-2x.bmp
WizardSmallImageFile=wizard-small-1x.bmp,wizard-small-2x.bmp
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "startup"; Description: "Start PR7-CB with Windows (it remembers what you copy while it runs)"; GroupDescription: "Windows:"
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\PR7-CB\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\Paragon PR7-CB"; Filename: "{app}\PR7-CB.exe"; Comment: "Clipboard history"
Name: "{autodesktop}\Paragon PR7-CB"; Filename: "{app}\PR7-CB.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PR7-CB.exe"; Parameters: "--startup on"; Flags: runhidden waituntilterminated; Tasks: startup
Filename: "{app}\PR7-CB.exe"; Parameters: "--startup off"; Flags: runhidden waituntilterminated; Tasks: not startup
Filename: "{app}\PR7-CB.exe"; Description: "{cm:LaunchProgram,Paragon PR7-CB}"; Flags: nowait postinstall skipifsilent
; Updates (Check for updates runs this installer with /SILENT /relaunch=1): start PR7-CB again when done.
Filename: "{app}\PR7-CB.exe"; Parameters: "--tray"; Flags: nowait runasoriginaluser; Check: Relaunch

[UninstallRun]
Filename: "{app}\PR7-CB.exe"; Parameters: "--unregister"; Flags: runhidden waituntilterminated; RunOnceId: "Unregister"

[Code]
// True only when the updater asked for it (/relaunch=1): normal and CI installs behave as before.
function Relaunch: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;
