# Decisão 003 · Aplicativo de computador: tecnologia e forma

- Data: 2026-10-09
- **Decisão: aplicativo local em Python, com interface em PySide6 (Qt), núcleo sem interface, um jogo por banco SQLite e observação da pasta de capturas por consulta periódica.**
- Detalhes da arquitetura: `docs/arquitetura.md`.

## Contexto
A camada de análise (OCR, regras, dicionário, LLM, grafo, vault) existe em Python e depende de Tesseract, OpenCV e FFmpeg. Falta transformá-la em algo que um jogador use sem linha de comando: escolher a pasta onde o jogo grava as capturas, deixar o programa processar o que chega, ver o grafo e abri-lo no Obsidian. O computador-alvo é o do jogador (o de teste tem Ryzen 5 5500, 16 GB e RX 7600 8 GB, `docs/hardware.md`), e o processamento é assíncrono, depois da captura.

## Alternativas consideradas
| Opção | A favor | Contra |
|---|---|---|
| **Python + PySide6 (escolhida)** | uma linguagem só, reaproveita o pipeline sem ponte; janela nativa; empacota com PyInstaller; LGPL | visual menos moderno que web; desenhar o grafo exige trabalho (fica para depois) |
| Electron ou Tauri + Python como processo auxiliar | interface web rica, bibliotecas de grafo prontas (Cytoscape) | duas linguagens, comunicação entre processos, empacotamento duplo; Electron pesa ~150 MB |
| Servidor local (FastAPI) + navegador ou pywebview | interface web, mesma API serviria a um acesso remoto | servidor, porta e ciclo de vida a gerenciar; pywebview depende de pythonnet no Windows, frágil no Python 3.14 |
| C#/.NET (WPF/WinUI) | nativo no Windows | reescrever ou embutir o pipeline em Python; só Windows |

## Por que assim
1. **O valor está no pipeline, que é Python.** Qualquer outra pilha obriga a manter uma ponte entre processos; com PySide6 a janela chama o núcleo diretamente.
2. **Núcleo sem Qt.** Regras, banco e orquestração não importam a interface. A mesma lógica serve à janela, à linha de comando (`gamemind.py processar`, que também é o protótipo integrado das Semanas 13 e 14) e aos testes. Trocar a interface no futuro, por web por exemplo, não mexe no núcleo.
3. **SQLite por jogo.** É um arquivo só, sem servidor, transacional, e cabe na pasta do jogo (`jogos/<nome>/`, ao lado do programa, com o vault dentro). Guarda o que é caro de refazer (leitura de cada mídia, resposta do LLM). Anotações, grafo e vault são derivados e podem ser apagados.
4. **Consulta periódica da pasta em vez de avisos do sistema.** Funciona com OneDrive e pastas de rede, onde os avisos do sistema falham, e não pede dependência extra. O custo, listar uma pasta a cada 10 s, é desprezível.

## Consequências
- Dependência nova só para a janela: `PySide6-Essentials` (`requirements-app.txt`). O núcleo e a CLI rodam sem ela.
- Tesseract e FFmpeg continuam externos. O empacotamento (POC II) precisa levá-los junto ou instalar; o Ollama segue como instalação à parte.
- O app não desenha nem lista o grafo: a janela mostra a captura em leitura e as notas do vault que vão sendo criadas, e o botão **Abrir no Obsidian** leva à exploração (Graph view e canvas). Atualizado em 2026-10-10 (antes havia uma aba Grafo).
