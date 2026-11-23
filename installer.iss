; Inno Setup Script untuk AutoLand Digitizer
; Menghasilkan installer Windows (.exe) profesional yang mandiri (offline)

#define MyAppName "AutoLand Digitizer"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Tim Digitalisasi Pertanahan"
#define MyAppExeName "AutoLandDigitizer.exe"

[Setup]
AppId={{C78923F4-2B44-48C7-B91F-7DEAC5632128}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=AutoLandDigitizer_Installer_v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "indonesian"; MessagesFile: "compiler:Languages\Indonesian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Seluruh file executable dan resource hasil PyInstaller
Source: "dist\AutoLandDigitizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Buat folder penyimpanan lokal
Source: "template\*"; DestDir: "{app}\template"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\dokumen_masuk"; Permissions: users-modify
Name: "{app}\temporary"; Permissions: users-modify
Name: "{app}\hasil_digitasi"; Permissions: users-modify
Name: "{app}\backup"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
