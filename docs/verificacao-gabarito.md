# Verificação do gabarito novo (A2)

Sorteio de 2026-10-08 (semente 20261008) entre os 30 itens de imagem e os 9 clipes anotados como rascunho de IA depois da verificação de 2026-10-07. Para cada item, abra a mídia em `data/raw/`, **sem olhar a anotação primeiro**, liste o que você anotaria seguindo `docs/gabarito.md` (regras 1 a 14) e só então compare com a anotação abaixo. Marque o resultado e anote as diferenças.

Critério de aprovação (como em 2026-10-07): nenhum erro de entidade ou relação nos 6 itens; se houver erro, corrigir o JSON, procurar o mesmo padrão nos outros itens do mesmo tipo e sortear mais 3.

## `img_058_glossario.jpg` (glossario)

Entidades anotadas:
- Cirilla (personagem): lista lateral: Cirilla
- Dandelion (personagem): lista lateral: Dandelion
- Eskel (personagem): lista lateral: Eskel
- Geralt de Rívia (personagem): lista lateral: Geralt de Rívia
- Lambert (personagem): lista lateral: Lambert
- Vesemir (personagem): lista lateral: Vesemir
- Yennefer de Vengerberg (personagem): lista lateral: Yennefer de Vengerberg
- Kaer Morhen (local): texto: "fortaleza de Kaer Morhen"
- Escola do Lobo (faccao): texto: "o membro vivo mais velho da Escola do Lobo"

Relações anotadas:
- Vesemir relacionado_a Geralt de Rívia: texto: "instrutor rígido... na juventude de Geralt"
- Vesemir membro_de Escola do Lobo: texto: "o membro vivo mais velho da Escola do Lobo"

Observações do rascunho: Entrada aberta: VESEMIR.

Resultado: ☐ correto  ☐ corrigir  ·  Diferenças: 

## `img_061_glossario.jpg` (glossario)

Entidades anotadas:
- Cirilla (personagem): lista lateral: Cirilla
- Dandelion (personagem): lista lateral: Dandelion
- Eskel (personagem): lista lateral: Eskel
- Geralt de Rívia (personagem): lista lateral: Geralt de Rívia
- Lambert (personagem): lista lateral: Lambert
- Vesemir (personagem): lista lateral: Vesemir
- Yennefer de Vengerberg (personagem): lista lateral: Yennefer de Vengerberg
- Kaer Morhen (local): texto: "treinavam com espadas de madeira em Kaer Morhen"

Relações anotadas:
- Eskel relacionado_a Geralt de Rívia: texto: "Eskel e Geralt eram como dois irmãos"
- Eskel localizado_em Kaer Morhen: texto: "reunindo-se em Kaer Morhen quase todo inverno"

Observações do rascunho: Entrada aberta: ESKEL.

Resultado: ☐ correto  ☐ corrigir  ·  Diferenças: 

## `img_064_item.jpg` (item)

Entidades anotadas:
- Coruja-do-mato (item): tooltip: "CORUJA-DO-MATO / POÇÃO"

Relações anotadas:
- (nenhuma)

Observações do rascunho: Inventário, aba Poções.

Resultado: ☐ correto  ☐ corrigir  ·  Diferenças: 

## `img_066_item.jpg` (item)

Entidades anotadas:
- Carta de Yennefer (item): título: "CARTA DE YENNEFER"
- Yennefer de Vengerberg (personagem): assinatura: "Yennefer"
- Arbusteira (local): texto: "Vá à vila Arbusteira"
- Vizima (local): texto: "próxima a Vizima"

Relações anotadas:
- (nenhuma)

Observações do rascunho: Texto da carta aberto.

Resultado: ☐ correto  ☐ corrigir  ·  Diferenças: 

## `img_074_quadro_avisos.jpg` (outro)

Entidades anotadas:
- Bastien (personagem): texto: "meu irmão, Bastien"
- Pomar Branco (local): texto: "estrada para Pomar Branco"

Relações anotadas:
- (nenhuma)

Observações do rascunho: Quadro de avisos: "Irmão, Onde Estás?".

Resultado: ☐ correto  ☐ corrigir  ·  Diferenças: 

## `vid_033_dialogo.mp4` (dialogo)

Entidades anotadas:
- Goslav (personagem): 0:03 legenda: "Havia um menino... Goslav"
- Nenneke (personagem): 0:12 legenda: "Nenneke se recusou a me aceitar de volta"
- Grifo (criatura): 0:32 legenda: "O grifo fez isso com ela?"
- Geralt de Rívia (personagem): 0:32 quadro com Geralt falando, sem rótulo de nome

Relações anotadas:
- (nenhuma)

Observações do rascunho: Rascunho a verificar. Tempos aproximados (±2 s). ATENÇÃO regra 9: Geralt não tem nome escrito neste clipe; anotação duvidosa, remover se a regra for aplicada à risca.

Resultado: ☐ correto  ☐ corrigir  ·  Diferenças: 

## Fechamento

- [x] Verificação concluída em 2026-10-08: gabarito confirmado como correto pelo autor, sem correções; `python scripts/validar_gabarito.py data/gabarito` com 0 problemas
- [x] "Rascunho" trocado por "verificado" em `docs/gabarito.md`, README e nas observações dos JSON
