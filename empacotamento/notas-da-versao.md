Primeira versão de teste (beta) do GameMind. Ele lê as capturas de tela e os clipes de um jogo, aprende os nomes desse jogo e monta um grafo de conhecimento num vault do Obsidian. Também traz um chat que responde perguntas com base no que foi lido.

## Baixar
| Sistema | Arquivo |
|---|---|
| Windows 10/11 (64 bits) | `GameMind-v0.1.0-beta-windows-x64.zip` |
| Linux (64 bits; testado no Ubuntu 22.04 ou mais novo) | `GameMind-v0.1.0-beta-linux-x64.tar.gz` |

**Windows:** extraia o zip numa pasta em que você possa gravar, por exemplo em Documentos (não em Arquivos de Programas), e abra `GameMind.exe`. O executável não é assinado. Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações > Executar assim mesmo**.

**Linux:** rode `tar -xzf GameMind-v0.1.0-beta-linux-x64.tar.gz` e depois `./GameMind/GameMind`. Se faltar alguma biblioteca do Qt, instale-as com `sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libegl1`.

## O que instalar à parte
- **Tesseract OCR** (obrigatório), com o idioma dos seus jogos (ex.: Portuguese).
  - Windows: [instalador UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). O GameMind encontra o Tesseract na pasta padrão.
  - Linux: `sudo apt install tesseract-ocr tesseract-ocr-por`.
- **FFmpeg** (opcional): só é preciso para ler clipes de vídeo.
- **IA** (opcional, para relações, criaturas, itens, missões e o chat). Escolha uma:
  - **Ollama**, a IA local, gratuita, em que nada sai do computador: [ollama.com/download](https://ollama.com/download), depois `ollama pull qwen2.5:7b`.
  - **Claude Code**, com o login da sua assinatura Claude. Ele recebe só texto, nunca imagens.

O menu **Aplicativo > Verificar o computador** confere tudo isso. A **Ajuda** traz guias passo a passo.

## Novidades
- Biblioteca de jogos e um assistente para adicionar um jogo (pastas de capturas e IA), sem nada para configurar antes.
- Leitura das capturas com OCR. O GameMind aprende os nomes e, com o modelo de imagem do Ollama, as regiões de texto de cada jogo.
- Grafo e vault do Obsidian, com o Quadro da partida.
- **Chat com a IA** na página do jogo. Ele responde só com o que foi lido das suas capturas, sem spoilers de fora, e cada resposta aponta as capturas de origem.
- 8 temas, guias de ajuda e opção de apagar um jogo.

## Onde ficam os seus dados
- Os jogos ficam na pasta `jogos/`, ao lado do executável: banco, grafo e vault.
- As configurações ficam em `%LOCALAPPDATA%\GameMind` no Windows e em `~/.local/share/gamemind` no Linux.
- Para atualizar para uma versão nova, mantenha a pasta `jogos/`.

## Limitações conhecidas (beta)
- A qualidade foi medida principalmente com um jogo em português. Outros jogos e idiomas ainda são pouco testados.
- Sem atualização automática nem instalador: é uma pasta portátil.
- No Windows, o executável não mostra o texto dos comandos de terminal (`GameMind.exe processar ...`). Para usar a linha de comando, rode pelo código-fonte (veja o README).
- Com o Ollama, uma GPU de 8 GB carrega um modelo de 7B por vez. A troca entre o modelo de texto e o de imagem leva uns 20 s.

Encontrou um problema? Abra uma issue com o que aconteceu e o conteúdo de **Aplicativo > Registro**.
