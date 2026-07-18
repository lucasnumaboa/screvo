# Screvo — Checklist de Testes

Rode o app a partir do código: `python main.py`
(algumas funções instalam dependências na 1ª vez — precisa de internet).

Marque cada item conforme testar.

---

## 1. Templates de resumo
- [ ] Aba **IA** → aparece o campo **Template de Resumo** com opções (Resumo geral, Ata de reunião, Tutorial, Documentação técnica, Lista de tarefas, Changelog).
- [ ] Escolher um template e clicar **Resumir IA** num vídeo com legenda → o resumo sai no formato escolhido.
- [ ] Trocar o template e resumir de novo → formato muda.

## 2. Chat sobre o vídeo
- [ ] Botão **Chat** aparece em cada vídeo (habilitado só quando há legenda).
- [ ] Clicar abre a janela de chat; digitar uma pergunta e receber resposta baseada na transcrição.
- [ ] Fazer uma 2ª pergunta de acompanhamento → a IA considera o contexto anterior.
- [ ] Pergunta sobre algo que não está no vídeo → responde que não encontrou.

> Requer provedor + API key configurados na aba IA.

## 3. Exportar resumo (.md / .docx / .pdf)
- [ ] Abrir um resumo (**Ver Resumo IA**) → botão **⤓ Exportar**.
- [ ] Exportar como **.md** → arquivo abre com o Markdown.
- [ ] Exportar como **.docx** → abre no Word com títulos/listas.
- [ ] Exportar como **.pdf** → PDF formatado.

> `.docx` usa `python-docx` e `.pdf` usa `reportlab` — instalados automaticamente
> na 1ª exportação (rodando do código-fonte).

## 4. Timestamps clicáveis
- [ ] Criar legenda de um vídeo (**Criar Legenda**) → gera também um `*.segments.json`.
- [ ] **Assistir** o vídeo → painel da legenda mostra trechos com `[mm:ss]` em rosa.
- [ ] Clicar num `[mm:ss]` → o vídeo pula para aquele momento e toca.

## 5. Identificação de quem falou (diarização) — OPCIONAL
- [ ] Se os modelos de diarização estiverem instalados, a legenda mostra "Falante 1/2..." nos trechos.
- [ ] Sem os modelos, a transcrição funciona normal (só sem rótulo de falante).

> Precisa colocar 2 modelos em `%APPDATA%\VideoRecorder\models\diarization\`:
> `segmentation.onnx` e `embedding.onnx` (links no topo de `diarizer.py`).
> É best-effort — se não tiver os modelos, é simplesmente ignorado.

## 6. Marcadores durante a gravação
- [ ] Iniciar uma gravação → no overlay aparece o botão **📌**.
- [ ] Clicar em 📌 algumas vezes durante a gravação (mostra "Marcador adicionado").
- [ ] Parar a gravação → é criado um arquivo `*.markers.txt` com os horários marcados.

## 7. Gravar região da tela
- [ ] Atalho/overlay → tela **Selecionar Conteúdo** → botão **▭ Região**.
- [ ] Arrastar um retângulo na tela; **Enter** (ou duplo clique) confirma, **Esc** cancela.
- [ ] A gravação captura só a região selecionada.

## 8. OCR — texto da tela
- [ ] Botão **Ler Tela (OCR)** em cada vídeo → confirma e processa.
- [ ] Ao terminar, vira **Ver Texto Tela** e cria `*_tela.txt` com o texto que aparecia na tela, por timestamp.
- [ ] Abrir **Ver Texto Tela** → mostra o texto capturado.

> OCR é 100% local. Usa o `winocr` (OCR nativo do Windows, instalado
> automaticamente do código-fonte) ou o **Tesseract** se estiver instalado.
> Se nenhum motor estiver disponível, mostra uma mensagem explicando como instalar.

## 9. Player de áudio embutido
- [ ] Em cada vídeo, abaixo dos botões, aparece a barra **▶ Ouvir áudio** com slider e tempo.
- [ ] Clicar em **Ouvir áudio** reproduz o áudio do vídeo ali mesmo (vira **⏸ Pausar**).
- [ ] O slider mostra o progresso e permite arrastar para navegar.
- [ ] (O botão antigo "Extrair Áudio" foi removido.)

## 10. Relatório Completo
- [ ] Botão **★ Relatório Completo** num vídeo.
- [ ] Ele executa em sequência: **criar legenda → ler tela (OCR) → montar relatório com IA** (a barra de status mostra "Etapa 1/3", "2/3", "3/3").
- [ ] Ao terminar, abre um relatório em Markdown com **capturas do vídeo embutidas** no corpo (a IA escolhe os momentos).
- [ ] É criado `*_relatorio.md` na pasta + uma subpasta `*_relatorio_arquivos/` com as imagens.
- [ ] O botão vira **Ver Relatório** (reabre sem regerar).
- [ ] No relatório, botão **⤓ Exportar** → **.md / .docx / .pdf** — as imagens aparecem no docx e no pdf.
- [ ] Renomear/Mover/Excluir o vídeo leva junto o relatório e a pasta de imagens (e conserta os links no rename).

> Requer IA configurada. Se um vídeo já tem legenda/OCR, o relatório reaproveita
> e pula essas etapas.

## 11. IA local no app (Gemma)
- [ ] Aba **IA** → seção **IA LOCAL NO APP · GEMMA** mostra seu hardware (ex.: "GPU: AMD Radeon RX 580 (8 GB) • RAM: 16 GB").
- [ ] A GPU exibida é a que está **realmente instalada** agora (não uma antiga).
- [ ] O combo de modelos Gemma marca o **⭐ recomendado** conforme a RAM; modelos que pedem mais RAM ficam desabilitados (o mais leve sempre fica ativo).
- [ ] Clicar **Baixar / Usar modelo** baixa o GGUF com barra de progresso e, ao final, mostra "Modelo pronto" (instala o `llama-cpp-python` na 1ª vez).
- [ ] Depois de baixar, **Resumir IA / Chat / Relatório** funcionam **sem API key** (provedor "IA local"), tudo dentro do app.

> Roda 100% no app, sem programas externos. A geração é por CPU — modelos
> maiores são mais lentos. Não precisa de Ollama.

---

## Regressão (o que já existia deve continuar OK)
- [ ] Gravar tela cheia / monitor específico / janela.
- [ ] Renomear, Mover (entre pastas), Excluir vídeo — levam junto legenda, resumo, segmentos, texto da tela e marcadores.
- [ ] Criar/Ver Legenda, Resumir IA/Ver Resumo IA, Copiar conteúdo.
- [ ] Cantos arredondados da janela, arrastar pela barra de título, redimensionar.

---

## Observações
- No **executável empacotado** (PyInstaller), as instalações automáticas de
  `python-docx`, `reportlab` e `winocr` **não** funcionam — para o build final,
  inclua esses pacotes no `.spec`/`requirements` se quiser docx/pdf/OCR no exe.
- Rodando a partir do código-fonte (`python main.py`), tudo se auto-instala.
