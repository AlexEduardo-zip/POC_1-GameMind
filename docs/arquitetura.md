# Arquitetura do aplicativo GameMind

Estado em 2026-10-10: núcleo, linha de comando e janela, **sem nenhuma configuração prévia ou específica de jogo**. Decisões: tecnologia em `docs/decisoes/003-aplicativo-desktop.md`, dicionário aprendido em `004`, nada específico de jogo em `005`.

## 1. O que o aplicativo faz
O jogador cria o jogo e indica a pasta onde as capturas e os vídeos dele são gravados. O GameMind lê o texto de cada screenshot ou clipe novo (OCR), aprende os nomes do jogo (personagens, locais, facções) e, com IA local, acrescenta criaturas, itens e relações; mantém um grafo do jogo, exportado como vault do Obsidian. Tudo roda no computador do jogador. O Claude (pelo login da assinatura) é opcional e recebe só texto.

**Fora desta fundação:** captura própria de tela (atalho global), instalador, desenho do grafo dentro do app e consulta em linguagem natural. A seção 12 diz onde cada um entra.

## 2. Requisitos que moldaram a arquitetura
| Requisito | Consequência no desenho |
|---|---|
| Local e privado | dados numa pasta do usuário; nada sai do computador sem o Claude ligado, e mesmo assim só o texto do OCR |
| Hardware modesto (OCR na CPU, LLM de 7B na GPU de 8 GB) | processamento assíncrono, depois da captura; OCR em paralelo e LLM em série |
| Incremental | só a mídia nova é lida; o que é caro (OCR, LLM) fica guardado e não é refeito |
| Nomes aprendidos no lote (o dicionário vale para todas as mídias, inclusive as lidas antes dele) | separação entre **leitura por mídia** (cara, guardada) e **consolidação do jogo** (barata, refeita sempre) |
| Tolerante a falhas | uma mídia com erro não para a rodada; a IA fora do ar não impede o grafo; cancelar não perde o que já foi lido |
| Sem spoiler | o grafo só contém o que apareceu nas capturas do jogo; não há base externa do jogo |
| IA plugável | uma interface só (`Backend.extrair` e `perguntar`) para o Ollama e o Claude pelo login da assinatura (Claude Code; `docs/ia-publica.md`); as IAs cobradas por token foram retiradas por enquanto |
| Independente de jogo | nenhuma lista de nomes, região calibrada ou regra de tela de um jogo (decisão 005) |

## 3. Visão geral
```
  janela (ui/, PySide6)          linha de comando (cli.py)      <- só apresentam e chamam o núcleo
             |                             |
             v                             v
  +------------- núcleo (src/gamemind/nucleo, sem Qt) --------------+
  |  observador -> registro -> leitura -> IA -> consolidação         |
  |               (novas)     (por mídia) (opc.) (jogo inteiro)      |
  |                                    -> grafo -> vault             |
  |                                                                  |
  |  repositorio: Jogo = pasta   + gamemind.db (SQLite)             |
  +--------------------------------+---------------------------------+
                                   | importa sem modificar
                                   v
  camada de análise: src/extracao (ocr, preprocessamento, gazetteer, llm, ia_publica, video),
  src/schema.py, src/grafo.py, src/exportar_vault.py
```
Externos: Tesseract (OCR), FFmpeg (clipes), Ollama ou API de IA (opcionais), Obsidian (para ler o vault).

## 4. Módulos
| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `gamemind.py` | ponto de entrada: sem argumentos abre a janela; com comando, CLI | `gamemind.cli` |
| `nucleo/recursos.py` | caminhos do programa e do usuário; extensões aceitas | — |
| `nucleo/config.py` | configuração global (IA, paralelismo, intervalo do vídeo, idioma do OCR) em `config.json` | recursos |
| `nucleo/repositorio.py` | `Jogo`: pasta, banco SQLite, mídias, leituras, respostas do LLM, anotações | recursos |
| `nucleo/dicionario.py` | aprende o dicionário de nomes do texto lido (falante de legenda, contexto, repetição); `dicionario.json` do jogo | `extracao.gazetteer` |
| `nucleo/regioes.py` | regiões de leitura do jogo (`regioes.json`): padrões genéricos, refinados uma vez pelo modelo de imagem | `extracao.ocr` |
| `nucleo/visao.py` | acha o modelo com visão no Ollama e marca na captura as linhas lidas | Ollama local |
| `nucleo/leitura.py` | etapa cara por mídia: o texto da tela inteira e dos recortes (OCR); clipes por quadro | `extracao` |
| `nucleo/consolidacao.py` | etapa barata do jogo inteiro: anotação base pelos nomes do dicionário e soma do LLM validado | `extracao` |
| `nucleo/canvas.py` | canvas do Obsidian (JSON Canvas) e miniaturas das capturas | `exportar_vault` (nomes), Pillow, FFmpeg |
| `nucleo/pipeline.py` | orquestra uma rodada; progresso, cancelamento, relatório; grafo e vault | todos acima, `grafo`, `exportar_vault` |
| `nucleo/obsidian.py` | abre o vault ou uma nota no Obsidian: o Obsidian só abre por link os vaults que conhece, então o vault do jogo é registrado no `obsidian.json` dele quando falta (só com o Obsidian fechado; aberto, o app explica como abrir a pasta como cofre) | — |
| `nucleo/observador.py` | detecta mídia nova e estável na pasta de capturas | pipeline (tipos) |
| `nucleo/chat.py` | chat sobre o jogo: base com o grafo (entidades, resumos, relações) e o texto de cada captura; busca por nome, outro nome, grafia parecida e palavras; pedido à IA do jogo só com isso, citando as capturas; conversa em `chat.json` | grafo, repositório, IA do jogo |
| `nucleo/diagnostico.py` | verifica Tesseract (e o idioma configurado), FFmpeg, Ollama e Claude Code; teste real da IA | `extracao.ia_publica` |
| `cli.py` | comandos `processar`, `jogos`, `diagnostico`, `limpar`, `exportar-anotacoes` | núcleo |
| `ui/tarefas.py`, `ui/espera.py` | ponte entre núcleo e Qt: QThread, sinais, log na janela; janela de espera modal com os passos do que demora (testar a IA, modelo de imagem, verificar o computador, fechar durante a leitura) | PySide6, núcleo |
| `ui/janela.py`, `ui/biblioteca.py`, `ui/assistente.py`, `ui/ajuda.py`, `ui/chat.py` | janela: biblioteca de jogos, assistente de novo jogo (questionário), página do jogo (com a aba de chat) e menu | PySide6, núcleo |
| `ui/temas.py`, `ui/aparencia.py` | temas da janela: cada tema é só cores, opacidades e arredondamento (`raio` dos controles e painéis, `raio_cartao` dos cartões) numa folha de estilo única (padrão: Hydra, nas cores e cantos do Hydra Launcher; espaçamento de todos numa grade de 8 px); escolha em Aplicativo > Tema, gravada em `config.json`; o logo (à esquerda do menu e ícone da janela) é desenhado em código nas cores do tema | PySide6 |

Regra de dependência: `ui` e `cli` conhecem o núcleo; o núcleo não conhece nenhum dos dois; a camada de análise não conhece o aplicativo.

## 5. Uma rodada de processamento
1. **Registro.** Lista a pasta de capturas. Arquivo novo vira `midia` pendente; arquivo que mudou de tamanho volta a pendente e perde a resposta do LLM antiga.
2. **Releitura por versão.** Mídias com erro, ou lidas por uma versão antiga do extrator (`VERSAO_LEITURA`), voltam a pendente.
3. **Leitura** (pendentes). O texto de cada mídia: OCR da tela inteira e de 3 recortes (legenda, objetivo, avisos; regiões genéricas de `regioes.json`). Imagens em paralelo (`workers` threads; o Tesseract roda em processos próprios); clipes um por vez, cada um com os quadros em paralelo, um quadro a cada `intervalo_video_s`, no tamanho do próprio vídeo. O resultado vai para o banco em JSON. Uma falha marca a mídia como `erro` e a rodada segue.
3b. **Regiões de leitura**, durante a própria leitura (rodada com IA, uma vez por jogo, se houver modelo com visão no Ollama). As pendentes são lidas em ordem sorteada; cada captura lida que parece cena (pouco texto na tela inteira e algum texto lido, contando os recortes) vai logo ao modelo, que aponta as linhas de legenda, objetivo e aviso, e as regiões são reestimadas. Para quando duas estimativas seguidas não fazem ajuste expressivo (ou em 8 amostras, ou no prazo); daí em diante, o que falta ler já usa as regiões novas. A região só cresce a partir da genérica e fica no `regioes.json` do jogo. Cada leitura guarda com que regiões foi feita: no fim, só os recortes desatualizados são relidos.
4. **Dicionário e base.** Com o texto de **todas** as mídias do jogo, `dicionario.aprender()` descobre os nomes (decisão 004). Os indícios são do português, não do jogo: em outro idioma, o dicionário depende mais da repetição e da IA. A anotação base de cada mídia são os nomes do dicionário que aparecem no texto dela (clipe: contados por quadro).
5. **IA** (se configurada). Para cada mídia sem resposta guardada **desta** IA, uma chamada com o texto por região e os nomes já detectados. A resposta crua é guardada. Se a IA falha, a rodada para de chamar e o grafo sai sem o restante; na próxima rodada continua de onde parou.
6. **Soma do LLM.** `normalizar()` valida cada resposta (lastro no texto, ontologia, nomes do dicionário). Nomes que o LLM acha em duas ou mais mídias entram no dicionário (`origem: ia`) e a base é refeita. Se a IA discorda do tipo de um nome aprendido pelo texto (2+ capturas, maioria), vale o tipo dela.
7. **Grafo.** `fundir()` junta as anotações na ordem de captura (`grafo.json`). Formas do mesmo nome (forma completa, plural, tratamento, palavra genérica + nome, mesma grafia sem espaço ou com erro de leitura) viram um nó só (`dicionario.unificar`). "Relacionado a" tirado de tela de lista (glossário, diário) só vale confirmado em 2 capturas.
7b. **Revisão das entidades** (com IA que responde perguntas livres, hoje o Ollama local; `resumos.py`). Em lotes, a IA vê, para cada entidade, o texto lido de todas as capturas dela e os nomes parecidos, e devolve uma frase de resumo, o tipo certo (ou "não é entidade") e se é outra grafia de um dos parecidos. Travas: só descarta o que foi visto em até 2 capturas, só absorve variante rara num nome mais visto, nunca mexe no dicionário manual. Guardada em `resumos.json`; refeita só quando o texto muda.
8. **Canvas e miniaturas.** `canvas.gerar()` desenha o quadro do mundo da partida, monta o contexto que vai nas notas de personagens, criaturas, facções e lugares (seção 9.1) e grava as miniaturas das capturas em `_midia/`.
9. **Vault.** `exportar()` escreve as notas, com o contexto do passo anterior (link para o mundo, capturas, vistos nas mesmas telas). O que o GameMind gerou antes (notas, canvas, miniaturas) e sumiu do grafo é apagado (manifesto `.gamemind-notas.json`); qualquer outro arquivo do vault fica.

Cancelar vale entre mídias: o que foi lido fica guardado.

## 6. Dados
```
%LOCALAPPDATA%\GameMind\config.json    IA, paralelismo, intervalo do vídeo, último jogo (Linux: ~/.local/share/gamemind)

<raiz do programa>\jogos\<jogo>\      (a pasta do .exe quando empacotado; GAMEMIND_DADOS sobrescreve a raiz)
├── gamemind.db                     SQLite (abaixo)
├── dicionario.json                 nomes aprendidos (derivado; refeito a cada rodada)
├── regioes.json                    recortes de leitura: criado com os genéricos; refinado pelo modelo de imagem, se houver
├── dicionario_manual.json          opcional, nunca necessário: nomes acrescentados à mão
├── grafo.json                      derivado
└── vault\                          derivado: é o vault do Obsidian do jogo (não há escolha de pasta)
```
| Tabela | Conteúdo | Refazer custa |
|---|---|---|
| `meta` | pasta de capturas, versão do esquema | — |
| `midia` | caminho, tipo, tamanho, data (ordem do jogo), estado, erro, versão e JSON da leitura, tempo | OCR: poucos segundos por imagem; clipe ≈ metade da duração |
| `llm` | resposta crua por (mídia, IA) | alguns segundos por mídia no 7B local, ou custo de API |
| `anotacao` | anotação final por mídia (formato do gabarito) | milissegundos (derivada) |

As mídias **não são copiadas**. Apagar um jogo é apagar a pasta dele.

## 7. Concorrência
- A interface nunca bloqueia: a rodada roda numa `QThread` e envia progresso por sinal. O banco tem uma conexão com trava, para uso entre threads.
- Uma rodada por vez por janela. Se chega captura nova durante uma rodada, outra roda ao fim (`de_novo`).
- O observador da janela é um `QTimer` na thread da interface: só lista a pasta e dispara a rodada. Na CLI (`--observar`) é um laço simples.
- Arquivo só é dado como pronto quando o tamanho não muda entre duas consultas; um clipe ainda sendo gravado não é lido pela metade.

## 8. Pontos de extensão
| Para... | Mexa em |
|---|---|
| nova IA | subclasse de `Backend` em `src/extracao/ia_publica.py` (`docs/ia-publica.md`) |
| novo jogo ou idioma | nada a escrever: crie o jogo na janela (**Novo jogo**) ou com `--jogo`; o idioma do OCR é a configuração `idioma_ocr` |
| nova fonte de captura | qualquer coisa que grave arquivos numa pasta já funciona; captura própria entra como um produtor de arquivos para a mesma pasta |
| mudança no extrator | suba `VERSAO_LEITURA` em `leitura.py`: as mídias antigas são relidas na próxima rodada |
| outro formato de saída | depois de `fundir()` em `pipeline._gerar` (o `grafo.json` já é a saída em JSON) |

## 9. Interface
Um jogo por pasta, criada pelo usuário (**Novo jogo**; a lista mostra os jogos que existem em `jogos/`). O grafo não é desenhado no app: explora-se no Obsidian.

| Tela | O que tem |
|---|---|
| Biblioteca (inicial) | um cartão por jogo (capa = ícone do .exe do jogo, ou a captura mais recente; o **⋯** abre ou apaga o jogo) e, do mesmo tamanho, **+ Adicionar jogo** |
| Assistente (Adicionar jogo; Jogo > Configurar jogo) | uma pergunta por tela, com transição: nome (ou um dos jogos instalados, lidos dos registros da Steam, Epic e GOG em segundo plano; ou o .exe escolhido à mão, para o ícone); pastas de screenshots e de vídeos (atalhos e seletor abertos nas pastas da Steam, NVIDIA, AMD Adrenalin e Xbox Game Bar; a pasta da Steam do jogo com o mesmo nome já vem preenchida); usar IA?; qual IA (Ollama ou Claude, com o botão de entrar com a conta) e o teste; aprender as regiões?; revisar e resumir as entidades? As escolhas valem só para aquele jogo (`Config.do_jogo`) |
| Página do jogo | **Iniciar leitura** (como o jogo foi configurado), **Acompanhar pasta** (botão com ícone de olho; ligado, lê sozinho o que aparecer nas pastas), **Abrir no Obsidian**, **⋯** (configurar, limpar vault, apagar o jogo), a captura em leitura e, ao lado, as abas **Notas** (do vault) e **Conversar com a IA** (só num jogo com IA; respostas só com o que foi lido, citando as capturas, que abrem na prévia; espera durante a leitura). Menu de cima: *Jogo* (configurar, abrir a pasta dos dados, limpar vault, apagar jogo, biblioteca) , *Aplicativo* (adicionar jogo, configurações gerais, verificar o computador, registro, tema), *Ajuda* (guias: primeiros passos, IA local com o Ollama, Claude, capturas, Obsidian, problemas comuns; F1) e *Sobre*. Durante a leitura, o que mexe no jogo ou começa outro trabalho fica desligado. Apagar um jogo apaga só `jogos/<jogo>/`; as capturas ficam |

### 9.1 Canvas (saída visual no Obsidian)
O foco é o **contexto do mundo**: lugares, personagens, facções e criaturas. **Missões ficam em segundo plano**, porque o jogo já as mostra (diário, mapa); o valor do GameMind está em lembrar *onde* e *com quem* as coisas aconteceram. O grafo costuma ter poucas relações entre essas entidades e muitas telas, então o contexto vem de três fontes, sempre distinguidas no desenho:
1. **Relações lidas** (`localizado_em`, `parte_de`, `membro_de`, `relacionado_a`), desenhadas como setas.
2. **Hierarquia de lugares** (`parte_de`): uma taverna fica dentro da vila que a contém.
3. **Vistos nas mesmas telas**, sem seta, porque aparecer junto não é relação afirmada. O peso de uma tela é 1/(outras entidades nela), e telas com mais de 6 entidades (glossário, mapa, diário) valem zero: lista não indica que estavam juntas. Só entra quem soma pelo menos 0,5.

```
vault/
├── Quadro da partida.canvas        o mundo: protagonistas no alto, uma coluna por lugar com o que pertence a ele, o resto embaixo
├── <Tipo>/<nome>.md                nota da entidade; personagem, criatura, facção e lugar trazem também capturas e "vistos nas mesmas telas"
└── _midia/*.jpg                    miniaturas 640x360 (imagem reduzida; de clipe, o quadro em que a entidade aparece)
```
- **Quadro da partida (o mundo):** só informação do jogo (nomes, capturas, descrições, relações lidas). A relevância de cada entidade (capturas em que aparece + relações, relativa à partida) só decide a posição e o tamanho:
  - no alto, lado a lado, os protagonistas (os personagens mais presentes), com capturas e descrição;
  - abaixo, uma coluna por lugar principal: o lugar em cima e, embaixo, os sublugares, as facções, os personagens e as criaturas ligados a ele (relação lida; senão, telas em comum). Facção sem lugar e com membros também vira coluna. A coluna mais pesada fica no meio;
  - embaixo, o restante em cartões menores (passado um limite, só links) e, por último, missões, itens, decisões e eventos em listas;
  - setas só para relações lidas entre vizinhos no quadro (mesma coluna, protagonistas, protagonista e cabeça de coluna); as demais ficam nas notas.
  - as descrições são os resumos da revisão (7b).
- **Contexto de uma entidade, na própria nota:** personagens, criaturas, facções e lugares trazem o link para o mundo, até 4 capturas e *Vistos nas mesmas telas*. Não há canvas por entidade (duplicava cada uma no vault).
- **Cores:** as do tema do Obsidian por tipo (verde personagem, ciano lugar, laranja facção, marrom criatura, amarelo item, vermelho decisão).
- **Cartões são as notas**, não cópias: clicar abre a nota.
- **Regerado a cada rodada:** ids estáveis, mas posições e conteúdo são refeitos. Anotações do jogador devem ficar num canvas próprio (que pode incorporar este).
- Custo: poucos segundos para refazer tudo, mais um quadro do FFmpeg na primeira vez de cada clipe; ~45 KB por miniatura.

**Limite honesto:** "vistos nas mesmas telas" é proximidade, não fato. Num grafo sem LLM ela responde por boa parte do que se vê no quadro; por isso fica sempre em grupo separado e rotulado, e quanto melhores as relações, menos o quadro depende dela.

## 10. Verificação
- `python -m unittest discover -s tests` roda testes offline do núcleo e do conector de IA: repositório, dicionário aprendido, regiões, consolidação, LLM com lastro, vault que preserva notas do usuário, erro de leitura, IA sem chave, abertura no Obsidian e observador. A janela não tem testes automáticos.
- `python scripts/avaliar_aplicativo.py` mede o aplicativo contra o gabarito (`data/gabarito`), em dados isolados, só com OCR e com a IA pedida (`--ia`), no conjunto `all` (`data/raw/all`: todas as screenshots e vídeos) ou `reduzido` (`data/raw/escopo_reduzido`, 15 capturas, mais rápido). Grava o resumo em `eval/resultado_<conjunto>.json`, as anotações em `eval/predicoes/` e **o vault gerado de cada configuração em `eval/vaults/<conjunto>_<configuração>/`** (abra uma delas como vault no Obsidian para comparar só OCR com OCR + IA).
- `python scripts/avaliar_duplicados.py [--ia ...]` confere, em `data/raw/escopo_reduzido` (15 capturas), se as formas do mesmo nome viram um nó só (gabarito em `data/gabarito_duplicados/`).
- O gabarito é de um jogo só e serve apenas para medir; o aplicativo não o usa.

### Teste geral (2026-10-10): todas as screenshots e vídeos
Conjunto `all`: 133 mídias (97 screenshots e 36 vídeos), qwen2.5:7b local, recortes genéricos, nomes aprendidos. Nenhuma mídia falhou. O gabarito cobre só parte das mídias (63); as demais são processadas, mas não entram na nota. "Acha" é a fração das entidades do gabarito que o programa encontrou; "acerta", a fração das que ele aponta que estão no gabarito (as ligações usam a mesma conta).

| | Só OCR | OCR + IA local |
|---|---|---|
| Tempo desta etapa | 18 min 53 s | + 15 min 55 s |
| Entidades no grafo / ligações / notas no vault | 31 / 0 / 31 | 120 / 25 / 120 |
| Nomes no dicionário aprendido | 31 | 44 (13 ensinados pela IA) |
| Entidades do gabarito: acha / acerta (de 100) | 30 / 63 | 61 / 60 |
| Entidades (F1) | 0,41 | 0,61 |
| Ligações: acha / acerta (de 100) | 0 / 0 | 13 / 24 |
| Ligações (F1) | 0,00 | 0,17 |
| Tokens da IA (entrada / saída) | — | 222 mil / 28 mil |

Acertos por tipo de entidade (o gabarito tem entre parênteses):

| Tipo | Só OCR | OCR + IA |
|---|---|---|
| personagem (107) | 35 | 84 |
| local (49) | 26 | 32 |
| facção (17) | 12 | 13 |
| criatura (19) | 0 | 15 |
| item (15) | 0 | 5 |
| missão (29) | 0 | 0 |
| decisão (7) | 0 | 0 |

Ligações que a IA acertou: `relacionado_a` 3 de 7, `localizado_em` 2 de 6 e `parte_de` 1 de 4; `ocorre_em` (0 de 12), `participa_de` (0 de 11), `obtido_em`, `concede` e `membro_de` não foram achadas.

Leitura:
- **Só OCR** acha uma parte pequena das entidades (os nomes que o dicionário aprende de legendas e repetições), mas o que aponta costuma estar certo; não produz criaturas, itens, missões, decisões nem ligações.
- **A IA dobra o que se acha** (de 30 para 61 de cada 100), sobretudo personagens e criaturas, e traz as primeiras ligações, mas aponta mais coisas erradas: muitas entidades a mais no grafo (120 contra 31), parte delas fora do gabarito. Itens e ligações ainda acertam pouco.
- **Missões e decisões não aparecem** com nenhuma configuração (decisão 005).
- A IA gastou em média cerca de 1.700 tokens de entrada e 210 de saída por mídia; ao todo, estimativa de uns US$ 0,11 a US$ 0,36 para esta rodada nos modelos baratos das três nuvens (preços de tabela, conferir).
- Reservas: o gabarito é pequeno e de um jogo, a IA varia entre execuções, e o aprendizado de nomes foi ajustado no mesmo material.

### Conclusões das medidas feitas durante o desenvolvimento
- As regras de tela de um jogo eram a única fonte de missões, decisões e relações; sem elas (decisão 005), essas três somem. As demais entidades vêm do dicionário aprendido e da IA.
- Os recortes de OCR valem a pena, mas recortes genéricos leem pior que recortes calibrados para um jogo.
- Sem IA, o dicionário aprendido perde para uma lista escrita à mão sobretudo em criaturas; com IA local a diferença cai bastante (decisão 004).
- Refinar as regiões só com a IA de texto piorou o resultado (rotula frase de menu como legenda); por isso vem desligado.
- Com o modelo de imagem (`qwen2.5vl:7b`, antigo conjunto reduzido de 23 capturas, rodada com IA): F1 de entidades 0,64 → 0,72 numa rodada; a variação entre rodadas iguais foi de até 0,04.
- Reservas: o gabarito é pequeno, a IA varia entre execuções e as regras de aprendizado foram ajustadas no mesmo material; os números tendem a ser otimistas.

## 11. Como rodar (desenvolvimento)
```bash
pip install -r requirements-app.txt          # requirements.txt + PySide6
python gamemind.py                           # janela
python gamemind.py diagnostico               # o que falta no computador
python gamemind.py processar --jogo "Meu jogo" --pasta "<pasta de capturas>" --ia ollama --observar
python gamemind.py exportar-anotacoes --jogo "Meu jogo" --saida eval/predicoes/app && python eval/avaliar.py --pred eval/predicoes/app
```
Executável: `empacotamento/gamemind.spec` (PyInstaller em modo pasta; `jogos/` fica ao lado do executável e `recursos.RAIZ` usa `sys._MEIPASS`). Uma tag `v*` dispara `.github/workflows/release.yml`, que testa, compila no Windows e no Linux e publica a release. Tesseract, FFmpeg, Ollama e Claude Code ficam fora do pacote: `extracao/__init__.py` acha o Tesseract na pasta padrão do Windows e esconde a janela de console dos programas externos (`SEM_JANELA`).

## 12. Evolução prevista
| Item | Onde entra | Observação |
|---|---|---|
| Instalador (POC II) | Inno Setup sobre o pacote do PyInstaller (seção 11) | levar Tesseract (Apache 2.0, com os idiomas) e FFmpeg (build LGPL) junto; Ollama continua instalação à parte |
| Captura própria | novo produtor de arquivos para a pasta observada (atalho global + captura de tela) | o núcleo não muda |
| Missões, decisões e relações sem regras de jogo | leitura com posição + IA de texto, ou IA que veja a imagem | hoje não há substituto das regras removidas (decisão 005; `docs/proximos-passos.md`) |
| Notas editáveis | seção do usuário preservada dentro das notas geradas (marcador no Markdown) | hoje a nota gerada é reescrita a cada rodada; notas próprias devem ficar em arquivos à parte |
| Grafo visual no app | `QWebEngineView` com Cytoscape.js ou `QGraphicsView` | só se o Graph view e os canvas do Obsidian não bastarem |
| Recortes nas miniaturas | só o trecho da captura onde a entidade aparece | hoje a miniatura é a captura inteira |
| Linha do tempo e resumo da sessão | nota gerada com a ordem de aparição (`primeira_vez`) e, com LLM, resumo só a partir das evidências | não depende das relações |
| Contexto de sessão | ligar decisões e itens à missão ativa | depende de achar missões |

## 13. Limites conhecidos da fundação
- Sem regras de tela, o app não acha missões nem decisões, e sem IA não acha criaturas, itens nem relações (10.1). Os recortes de OCR são genéricos e podem ler pior em jogos com interface fora do padrão.
- A ordem do tempo de jogo vem da data do arquivo: copiar capturas para outra pasta muda a data (as ferramentas de captura costumam pôr data e hora no nome, que poderia servir de alternativa).
- O nome do arquivo identifica a mídia nas fontes do grafo: dois arquivos de mesmo nome em pastas diferentes se confundem.
- A primeira rodada de um jogo com muitas capturas é longa (OCR na CPU); as seguintes só leem o que é novo.
- A interface ainda não foi testada por jogadores; os testes automáticos cobrem o núcleo, não a janela.
