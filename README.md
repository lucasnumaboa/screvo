# Screvo

**Screvo** é um gravador de tela leve para Windows que vai além de gravar: ele
**transcreve o áudio** de forma offline e ainda **resume o conteúdo com IA**.
O nome vem de *tela* + *escrevo* — grava a tela e transforma em texto.

Interface em PyQt6 com tema rosa, atalho global, overlay flutuante e ícone na
bandeja do sistema.

---

## ✨ Recursos

- 🎥 **Gravação de tela** com FFmpeg — múltiplos monitores ou janela específica.
- ⌨️ **Atalho global** configurável (padrão `Ctrl+Shift+R`) e overlay flutuante.
- 🔊 **Áudio do sistema + microfone** via WASAPI loopback (sem instalar nada),
  com controle de volume e opção de silenciar durante a gravação.
- ⚙️ Formatos `mp4`, `mkv`, `avi`, `webm`; FPS, qualidade e codec (`h264`/`h265`)
  ajustáveis.
- 🗣️ **Transcrição local (offline)** com o modelo NVIDIA **Parakeet TDT v3**
  (via `sherpa-onnx`) — o áudio nunca sai da sua máquina.
- 🤖 **Resumo por IA** das legendas, com provedor à escolha
  (**Gemini, Claude, OpenAI ou DeepSeek**). O resumo é gerado em **Markdown**.
- 🎬 **Gerenciador de vídeos**: assistir (player embutido), renomear, criar/ver
  legenda, resumir com IA, mover e excluir.
- 📁 **Grupos/pastas** para organizar as gravações — mover um vídeo leva junto a
  legenda e o resumo.
- 👀 **Visualizador integrado** de legendas e resumos (Markdown formatado), com
  botão **Copiar conteúdo**.

---

## 📦 Requisitos

- Windows 10/11 (x64)
- Python 3.10+ (para rodar a partir do código)
- FFmpeg (`ffmpeg.exe` e `ffprobe.exe`) — veja abaixo

As dependências Python estão em [`requirements.txt`](requirements.txt):

```bash
pip install -r requirements.txt
```

### FFmpeg

Os binários do FFmpeg **não** ficam no repositório (cada um passa de 100 MB, o
limite do GitHub). Baixe uma build em
[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) e copie
`ffmpeg.exe` e `ffprobe.exe` para `ffmpeg/bin/` (veja `ffmpeg/bin/LEIA-ME.txt`).

---

## ▶️ Executando a partir do código

```bash
python main.py
```

O app inicia na bandeja do sistema. Use o atalho (padrão `Ctrl+Shift+R`) para
abrir o seletor de gravação, ou dê dois cliques no ícone da bandeja para abrir
as configurações.

---

## 🏗️ Gerando o executável

Com [PyInstaller](https://pyinstaller.org/):

```bat
build.bat
```

O executável é gerado em `dist/Screvo.exe`.

Para gerar o **instalador** (requer [Inno Setup](https://jrsoftware.org/isdl.php)):

```bat
build_installer.bat
```

O instalador sai em `installer_output/`.

---

## 🤖 Configurando o resumo por IA

1. Abra a aba **IA** nas configurações.
2. Escolha o **provedor** (Gemini, Claude, OpenAI ou DeepSeek).
3. (Opcional) Informe o **nome do modelo** — em branco usa o padrão do provedor.
4. Cole a sua **API key**.

A chave fica salva **apenas no seu computador**
(`%APPDATA%\VideoRecorder\config.json`). Depois, na aba **Vídeos**, use
**Resumir IA** (disponível quando o vídeo já tem legenda). O resumo é salvo como
`<nome-do-video>_resumo.txt` na mesma pasta.

### Modelos padrão por provedor

| Provedor  | Modelo padrão                 |
|-----------|-------------------------------|
| OpenAI    | `gpt-4o-mini`                 |
| Claude    | `claude-3-5-sonnet-20241022`  |
| Gemini    | `gemini-1.5-flash`            |
| DeepSeek  | `deepseek-chat`               |

---

## 🗂️ Estrutura do projeto

| Arquivo                 | Descrição                                             |
|-------------------------|-------------------------------------------------------|
| `main.py`               | Ponto de entrada                                      |
| `app.py`                | Tray, hotkey global e ciclo de gravação               |
| `settings_window.py`    | Janela de configurações (todas as abas)               |
| `recorder.py`           | Gravação via FFmpeg                                   |
| `audio_capture.py`      | Captura do áudio do sistema (WASAPI)                  |
| `local_transcriber.py`  | Transcrição offline (Parakeet / sherpa-onnx)          |
| `ai_summarizer.py`      | Resumo por IA (Gemini/Claude/OpenAI/DeepSeek)         |
| `text_viewer.py`        | Visualizador de legenda/resumo (Markdown)             |
| `video_player.py`       | Player de vídeo embutido                              |
| `flow_layout.py`        | Layout responsivo (quebra os botões em telas menores) |
| `icons.py`              | Ícones vetoriais da sidebar e do app                  |
| `resources/`            | Ícone do app (`icon.ico`) e gerador                   |

---

## 🔒 Privacidade

- A **transcrição** roda 100% offline; o áudio não é enviado a nenhum servidor.
- O **resumo por IA** é a única funcionalidade que envia dados (o texto da
  legenda) para o provedor que **você** escolher, usando a **sua** API key.

---

## 📄 Licença

Distribuído sob a licença **MIT** — veja o arquivo [`LICENSE`](LICENSE).

O FFmpeg (usado pelo app) mantém sua própria licença LGPL/GPL.
