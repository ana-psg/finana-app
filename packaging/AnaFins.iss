; Instalador do AnaFins (Inno Setup 6). Gerar com build.ps1, que cria antes a pasta dist\AnaFins.
#define AppVersion "2.0.0"

[Setup]
AppId={{4E9A2C71-8B3D-4F06-A5E2-1C7D9B0F3A64}
AppName=AnaFins
AppVersion={#AppVersion}
AppVerName=AnaFins {#AppVersion}
AppPublisher=AnaFins
VersionInfoVersion={#AppVersion}
VersionInfoCompany=AnaFins
VersionInfoDescription=Instalador do AnaFins
VersionInfoProductName=AnaFins
; Instala só para o usuário atual: não pede administrador
PrivilegesRequired=lowest
DefaultDirName={autopf}\AnaFins
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=AnaFins-Setup-{#AppVersion}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\AnaFins.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; O AnaFins é uma janela comum: o Windows consegue fechá-la antes de atualizar ou desinstalar
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; Flags: unchecked

[InstallDelete]
; Atualização: tira os arquivos da versão antiga do programa. Os dados ficam em %APPDATA% e não são tocados.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\AnaFins\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; DestName: "Manual.md"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AnaFins"; Filename: "{app}\AnaFins.exe"
Name: "{autoprograms}\Manual do AnaFins"; Filename: "{app}\Manual.md"
Name: "{autodesktop}\AnaFins"; Filename: "{app}\AnaFins.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\AnaFins.exe"; Description: "Abrir o AnaFins agora"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    MsgBox('Seus dados não foram apagados. Eles continuam em:' + #13#10 + ExpandConstant('{userappdata}\AnaFins'), mbInformation, MB_OK);
end;
