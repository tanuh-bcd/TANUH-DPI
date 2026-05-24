[Setup]
AppName=Forgensic
AppVersion=1.0.0
DefaultDirName={pf}\Forgensic
DefaultGroupName=Forgensic
UninstallDisplayIcon={app}\Forgensic.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=Forgensic_Setup

[Files]
Source: "dist\Forgensic-Windows-x86_64.exe"; DestDir: "{app}"; DestName: "Forgensic.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\Forgensic"; Filename: "{app}\Forgensic.exe"
Name: "{group}\Uninstall Forgensic"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Forgensic"; Filename: "{app}\Forgensic.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
