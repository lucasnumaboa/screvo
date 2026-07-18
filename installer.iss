; ============================================================
; Screvo - Inno Setup Installer Script
; ============================================================
; Para compilar este instalador:
; 1. Instale o Inno Setup: https://jrsoftware.org/isinfo.php
; 2. Primeiro rode build.bat para gerar o exe
; 3. Abra este arquivo no Inno Setup Compiler
; 4. Clique em Build > Compile (ou Ctrl+F9)
; ============================================================

#define MyAppName "Screvo"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Screvo"
#define MyAppExeName "Screvo.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={commonpf}\Screvo
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=Screvo_Setup_{#MyAppVersion}
SetupIconFile=resources\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes
LicenseFile=
InfoAfterFile=

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na &Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "startupicon"; Description: "Iniciar com o &Windows"; GroupDescription: "Opcoes:"

[Files]
; Executável principal
Source: "dist\Screvo.exe"; DestDir: "{app}"; Flags: ignoreversion

; FFmpeg - binários necessários
Source: "ffmpeg\bin\ffmpeg.exe"; DestDir: "{app}\ffmpeg\bin"; Flags: ignoreversion
Source: "ffmpeg\bin\ffprobe.exe"; DestDir: "{app}\ffmpeg\bin"; Flags: ignoreversion
; Opcionais (não quebram o build se não existirem)
Source: "ffmpeg\bin\ffplay.exe"; DestDir: "{app}\ffmpeg\bin"; Flags: ignoreversion skipifsourcedoesntexist
Source: "ffmpeg\LICENSE"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist
Source: "ffmpeg\README.txt"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Menu Iniciar
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"

; Desktop
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Iniciar com Windows (se selecionado)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VideoRecorder"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
; Executar após instalação
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Limpa configurações
Type: filesandordirs; Name: "{app}\ffmpeg"
Type: dirifempty; Name: "{app}"

[Code]
// Verifica se já está instalado e oferece desinstalação
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  UninstallKey: String;
  UninstallString: String;
begin
  Result := True;
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';

  if RegQueryStringValue(HKLM, UninstallKey, 'UninstallString', UninstallString) then
  begin
    if MsgBox('Screvo ja esta instalado. Deseja desinstalar a versao anterior?',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec(RemoveQuotes(UninstallString), '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    end
    else
    begin
      Result := False;
    end;
  end;
end;

// Cria pasta de gravações padrão
procedure CurStepChanged(CurStep: TSetupStep);
var
  VideosDir: String;
begin
  if CurStep = ssPostInstall then
  begin
    VideosDir := ExpandConstant('{userappdata}\VideoRecorder');
    if not DirExists(VideosDir) then
      CreateDir(VideosDir);
  end;
end;
