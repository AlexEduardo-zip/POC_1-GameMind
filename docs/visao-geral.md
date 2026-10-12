# GameMind em linguagem simples

Para quem quer entender o projeto sem ler código nem tabelas técnicas: o que o aplicativo faz, como faz e o que esperar dele. Os números abaixo vêm do teste geral de 2026-10-10 (todas as screenshots e vídeos do material do projeto, com a IA local média) e mudam a cada nova rodada de medida (`scripts/avaliar_aplicativo.py`).

## 1. A ideia
Em jogos longos, o jogador esquece quem é quem, onde conheceu aquele personagem e o que aconteceu entre uma sessão e outra. Diários do jogo e wikis não ajudam muito: não sabem o que **você** viu e ainda podem dar spoiler.

O GameMind olha as capturas de tela e os vídeos que o próprio jogador grava e monta, sozinho, um **caderno de anotações da partida**: uma nota para cada personagem, lugar, facção, criatura e item, ligadas entre si. O caderno é aberto no **Obsidian**, onde também aparece o desenho do grafo de ligações. Como só usa o que apareceu na tela, o caderno **não revela nada que o jogador ainda não viu**.

O aplicativo funciona com qualquer jogo, sem nada preparado antes.

## 2. O que acontece por dentro, passo a passo
1. **Pegar as capturas.** Você cria o jogo no aplicativo e indica a pasta onde as capturas e os vídeos dele são gravados. O programa só trabalha nos arquivos novos e pode "observar" a pasta para processar sozinho o que chegar.
2. **Ler a tela.** Um leitor de texto (OCR) lê a tela inteira e três recortes genéricos, os mesmos para qualquer jogo: a faixa de baixo (legendas), o canto de cima à direita (objetivos) e o alto à esquerda (avisos). O texto miúdo é ampliado e clareado antes. Dos vídeos, o programa lê um quadro a cada 2 segundos.
3. **Aprender os nomes.** O programa monta sozinho um dicionário de nomes a partir do texto lido: quem fala numa legenda ("Nome: fala"), nomes que se repetem em várias telas e o contexto em volta ("para X", "tropas de X"). Ninguém escreve lista nenhuma.
4. **(Opcional) Pedir ajuda a uma IA.** Uma IA de linguagem recebe o texto lido e acha o que o dicionário não alcança (criaturas, itens) e ligações entre as coisas. Ela pode rodar no seu computador ou na nuvem, e nunca recebe imagens, só texto.
5. **Conferir.** Tudo o que a IA sugere passa por uma checagem: o tipo faz sentido? A ligação é permitida? **O nome está mesmo escrito na tela?** Esta última regra é a mais importante (seção 6).
6. **Montar o caderno.** Nomes repetidos viram um só ("Brisa" e "Brisalda"), e cada entidade vira uma nota. O programa também desenha um **quadro do mundo** (uma coluna por lugar, com quem foi visto ali) e um quadro de contexto para cada personagem, lugar, facção e criatura.

As imagens ficam onde estão, o que foi lido fica guardado num banco local e **só o que é novo é relido** na rodada seguinte.

## 3. Como é o aplicativo
Uma tela de trabalho: você cria ou escolhe o jogo, indica a pasta de capturas e aperta **Processar só OCR** ou **Processar com IA** (a IA escolhida na aba Configurações). Enquanto roda, a tela mostra de um lado **a captura que está sendo lida** e do outro **as notas do vault que vão sendo criadas**. Ao terminar, **Abrir no Obsidian** leva ao caderno.

Cada jogo tem a sua pasta, `jogos/<nome do jogo>/`, ao lado do programa, com o banco de dados, os nomes aprendidos e o vault. Nas Configurações você escolhe a IA (ou nenhuma), o idioma do texto dos jogos, e pode testar a conexão e verificar o computador.

## 4. Os modos de funcionamento
Só a etapa da IA muda de um modo para outro.

| Modo | O que faz | O que exige | Quando serve |
|---|---|---|---|
| **Só OCR** | lê o texto e reconhece os nomes que aprendeu | só o processador | teste rápido; acha personagens, lugares e facções, mas não criaturas, itens nem ligações |
| **IA local média** (7 bilhões de parâmetros) | acrescenta criaturas, itens e ligações e ensina nomes ao dicionário | placa de vídeo com cerca de 5 GB livres | melhor resultado, sem nada sair do computador |
| **IA local pequena** (3 bilhões) | o mesmo, com menos acerto nas ligações | placa de vídeo com cerca de 2 GB livres | computador mais fraco |
| **IA pública** (OpenAI, Gemini, Claude) | o mesmo, num servidor do provedor | internet, chave de API e pagamento por uso | sem placa de vídeo; qualidade ainda não comparada com a local |
| **Claude Code** (assinatura Pro/Max) | usa o login da assinatura em vez de chave | assinatura e login | testes; não serve para uso contínuo |

Em todos os modos com IA, ela recebe só o **texto lido da tela**, nunca as imagens, e a checagem da etapa 5 vale igual para a IA local e para a da nuvem.

## 5. O que o aplicativo acerta hoje
Teste geral: 133 mídias (97 screenshots e 36 vídeos), processadas só com OCR e depois com a IA local média, e comparadas com a resposta conferida à mão, que cobre parte delas. De cada 100 entidades que existem nas telas, quantas o programa **acha** e, entre as que aponta, quantas **acerta**:

| | Só OCR | OCR + IA local |
|---|---|---|
| Entidades que acha | 30 | 61 |
| Entidades que acerta | 63 | 60 |
| Ligações que acha | 0 | 13 |
| Ligações que acerta | 0 | 24 |
| Entidades no caderno (grafo e notas) | 31 | 120 |

Acertos por tipo, em quantas das entidades do gabarito cada configuração achou:

| Tipo | Só OCR | OCR + IA local |
|---|---|---|
| Personagem | 35 de 107 | 84 de 107 |
| Local | 26 de 49 | 32 de 49 |
| Facção | 12 de 17 | 13 de 17 |
| Criatura | 0 de 19 | 15 de 19 |
| Item | 0 de 15 | 5 de 15 |
| Missão | 0 de 29 | 0 de 29 |
| Decisão | 0 de 7 | 0 de 7 |

- **Só OCR:** acha poucas entidades, e as que aponta costumam estar certas. Personagens, lugares e facções, pelo dicionário aprendido; nada de criaturas, itens, missões, decisões nem ligações.
- **Com IA local:** acha o dobro, sobretudo personagens e criaturas, e traz as primeiras ligações, mas passa a apontar também coisas erradas (o caderno cresce de 31 para 120 entidades, parte delas fora da resposta conferida).
- **Missões e decisões não funcionam** em nenhum modo: exigiam regras sobre onde ficam o título da missão e as opções de diálogo na tela de um jogo específico, retiradas para o aplicativo servir a qualquer jogo (`docs/proximos-passos.md`).
- **As ligações ainda são fracas:** a IA acerta algumas de lugar e de parentesco entre lugares, e quase nenhuma entre missão e personagem.
- **Os recortes valem a pena** e recortes genéricos leem pior que recortes calibrados para um jogo.
- Cada configuração gera um vault do Obsidian, guardado em `eval/vaults/` para comparar.

## 6. O que o estudo de viabilidade ensinou
O estudo (`docs/estudo-viabilidade.md`) usou regras e um dicionário escritos para um jogo específico e mostrou o que continua valendo:
- **A IA precisa de lastro.** Quando a IA recebia a lista de nomes do jogo no pedido, passava a inventar personagens que não estavam na tela. O que resolveu não foi trocar de modelo, e sim exigir que **o nome esteja escrito no texto lido**. A regra vale para qualquer IA.
- **Ler bem a tela pesa mais que a IA** nas entidades; a IA serve sobretudo para as ligações e para o que o dicionário não alcança.
- **Vídeo, um quadro a cada 2 segundos.** Um quadro por vídeo perde quase tudo; um por segundo dobra o trabalho e acrescenta ruído.
- **Capturas e vídeos se completam.**

## 7. Custo e recursos

### 7.1 Tempo
No teste geral (133 mídias, 4 leituras em paralelo, computador com Ryzen 5 5500 e RX 7600):
- **Só OCR:** 18 min 53 s para as 97 screenshots e os 36 vídeos, quase tudo em vídeos.
- **Com a IA local média:** mais 15 min 55 s sobre a leitura já feita, cerca de 7 s por mídia.
- **Vídeo:** a leitura leva cerca de metade da duração do clipe com um quadro a cada 2 s.
- As rodadas seguintes só leem o que é novo, e tudo roda **depois** da sessão de jogo.

### 7.2 Recursos do computador
- **Processador:** o OCR usa só a CPU (4 processos). Sem IA, não precisa de placa de vídeo.
- **Placa de vídeo:** a IA local média ocupa cerca de **4,5 GB** de memória de vídeo e a pequena cerca de **2 GB**. Numa placa de 8 GB sobra pouco para jogar ao mesmo tempo; por isso o processamento é feito depois.
- **Disco:** as imagens não são copiadas; o banco guarda só texto, e cada miniatura do vault pesa dezenas de KB.
- **Instalação:** Tesseract (OCR, com o idioma do jogo) e FFmpeg (vídeo); o Ollama roda a IA local e só é preciso nesse modo.

### 7.3 Privacidade
Tudo roda no seu computador. Só no modo de IA pública sai algo, e é **só o texto lido** da tela, nunca imagem nem vídeo.

### 7.4 Preço estimado com IA pela internet
No teste geral, a IA local recebeu em média cerca de **1.700 tokens de entrada e 210 de saída por mídia** (222 mil e 28 mil nas 133 mídias; 1.500 tokens são mais ou menos duas páginas de texto). Com os modelos mais baratos de cada provedor, os padrões do aplicativo, e preços de tabela por milhão de tokens de entrada e saída (gpt-5-mini US$ 0,25 e 2,00; gemini-2.5-flash US$ 0,30 e 2,50; claude-haiku-4-5 US$ 1,00 e 5,00):

| Provedor (modelo padrão) | Estas 133 mídias | Mil mídias |
|---|---|---|
| OpenAI (gpt-5-mini) | cerca de US$ 0,11 | cerca de US$ 0,8 |
| Google (gemini-2.5-flash) | cerca de US$ 0,14 | cerca de US$ 1,0 |
| Anthropic (claude-haiku-4-5) | cerca de US$ 0,36 | cerca de US$ 2,7 |

É **estimativa**: os preços mudam e precisam ser conferidos; o conector ainda não foi usado com chaves reais (modelos que "pensam" antes de responder gastam mais na saída). A IA local não tem custo por uso, e o Claude Code pela assinatura consome a cota do plano.

### 7.5 Que modo escolher
| Prioridade | Modo |
|---|---|
| Rodar em qualquer computador | Só OCR (personagens, lugares e facções) |
| Melhor resultado sem mandar nada para fora | IA local média |
| Computador mais fraco | IA local pequena |
| Sem placa de vídeo e com internet | IA pública de modelo barato |

## 8. Limites
- **Um jogo só foi medido:** o aplicativo não usa nada específico de jogo, mas o gabarito é de um jogo. Falta medir em outro jogo e em telas novas.
- **Números de desenvolvimento:** a resposta conferida à mão é pequena e de um jogo, as regras de aprendizado de nomes foram ajustadas no mesmo material usado para medir, e a IA varia entre execuções; os resultados provavelmente são otimistas.
- **Sem missões, decisões e ligações** até haver um substituto das regras de tela que não dependa de jogo.
- **Recortes genéricos:** interfaces fora do padrão podem escapar deles.
- **A IA pública** ainda não foi comparada com a local.
- **Ainda não houve teste com jogadores.**
