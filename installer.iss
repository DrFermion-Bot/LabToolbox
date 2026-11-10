; LabToolbox Inno Setup installer (Windows x64)
;
; Build (from the repository root, after "pyinstaller labtoolbox.spec"):
;   iscc /DMyAppVersion=0.1.14 installer.iss
; GitHub Actions calls this automatically; see .github/workflows/release.yml.
;
; UNSIGNED BY DESIGN: no Authenticode code-signing certificate is used. Windows
; SmartScreen shows "Windows protected your PC" on first launch; users click
; "More info" -> "Run anyway". See docs/INSTALL.md.
;
; Chinese (Simplified) wizard messages: user-contributed Inno Setup translation
; by Zhenghan Yang (Kira) - https://github.com/kira-96/Inno-Setup-Chinese-Simplified-Translation
;
#ifndef MyAppVersion
  #define MyAppVersion "0.1.14"
#endif
#define MyAppName "LabToolbox"
#define MyAppExeName "LabToolbox.exe"
#define MyAppPublisher "DrFermion"
#define MyAppCopyright "MIT License - Ruinong Pan (DrFermion), University of Dundee"
#define MyAppURL "https://github.com/DrFermion/LabToolbox"
#define MyIcon "assets\labtoolbox.ico"

[Setup]
AppId={{8E3F1C2A-5B4D-4E6F-9A7B-2C3D4E5F6A7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppCopyright={#MyAppCopyright}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=LabToolbox biology lab analysis toolbox installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
DefaultDirName={autopf}\LabToolbox
DefaultGroupName=LabToolbox
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=LabToolbox-Setup-{#MyAppVersion}
SetupIconFile={#MyIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; The bundle includes a full Java runtime (~130 MB extracted), so require a bit of room.
; Signing (optional, requires a purchased code-signing certificate - not used for the
; current unsigned releases): set SignTool in [Setup] and run iscc /S<mytool>.
; SignTool=mysigntool
; SignedUninstaller=yes

[Languages]
; Chinese translation file is vendored in installer/languages/ (UTF-8 with BOM).
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimplified"; MessagesFile: "installer\languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; dist\LabToolbox\ already contains, inside imagej\:
;   ij.jar (ImageJ 1.54), jre\ (Temurin 11 Java runtime), scripts macro, licenses.
Source: "dist\LabToolbox\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#MyIcon}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\labtoolbox.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\labtoolbox.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent