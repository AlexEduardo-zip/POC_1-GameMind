# Estudo de viabilidade: conclusões

O estudo de viabilidade (POC I) testou, com *The Witcher 3* em português, como transformar capturas de tela e vídeos em entidades e relações. O código das rodadas (regras de tela, dicionário de nomes e scripts) era específico daquele jogo e foi retirado do projeto (decisão `docs/decisoes/005-sem-configuracao-por-jogo.md`); ficam as conclusões. Para consultar o código, está no histórico do repositório (commit `cd8e451`).

**Aviso:** regras, prompt e filtros foram ajustados sobre as mesmas imagens do gabarito (`docs/gabarito.md`), sem conjunto separado. As conclusões abaixo são de desenvolvimento e provavelmente otimistas; o estado atual do aplicativo está em `docs/arquitetura.md`.

## O que o estudo mostrou
1. **Dá para converter o conteúdo da tela em grafo útil com IA local e modesta**, em computador de consumo e com processamento depois da sessão de jogo.
2. **Ler bem a tela pesa mais que a IA nas entidades.** Recortes ampliados das regiões de texto pequeno (legenda, objetivo, avisos), com filtro que isola o texto claro de contorno escuro, melhoraram muito o OCR, sobretudo nas legendas. Ampliar só a tela inteira não ajuda e pode piorar.
3. **Regras sobre a estrutura da tela** (onde ficam o título da missão, a lista do diário, as opções de diálogo) foram o que fez aparecerem missões, decisões e as primeiras relações, que nenhum dicionário alcança. Por serem específicas de cada jogo, foram retiradas do aplicativo, e substituí-las é a principal pendência.
4. **A IA acrescenta as relações e pouco nas entidades.** Sozinha, inventa nomes (principalmente quando recebe a lista de nomes conhecidos no prompt). O que resolveu foi exigir **lastro no texto**: o nome precisa estar escrito no que foi lido, o tipo e a relação precisam ser permitidos pela ontologia. A regra vale para qualquer IA, local ou da nuvem.
5. **Modelo local pequeno ou médio:** o pequeno basta para entidades e ocupa metade da memória de vídeo, mas perde bastante nas relações; o médio (7 bilhões de parâmetros, quantizado) cabe numa placa de 8 GB.
6. **Vídeo:** um quadro por clipe não serve (texto de legenda, objetivo e aviso aparece e some); **um quadro a cada 2 segundos** é o ponto certo. Um quadro por segundo dobra o trabalho e acrescenta ruído. Capturas e vídeos se complementam: o vídeo traz o que acontece ao longo da cena.
7. **Busca de nomes exata é melhor que aproximada.** Tolerar erro de OCR na busca trouxe falsos positivos e nenhum acerto novo; a correção por semelhança só vale em nomes longos.
8. **Nunca construir a lista de nomes a partir do gabarito.** A primeira linha de base fez isso e o resultado parecia muito melhor do que era.
9. **Consolidar no lote exige cuidado:** regras que juntam grafias do mesmo nome, ajustadas num lote, podem errar em telas novas.
10. **Pontos fracos:** relações, itens, lugares fora do dicionário e telas com texto pequeno sobre a cena (mapa e HUD).

## Limites do estudo
- Sem conjunto separado de teste; falta medir em telas novas e em outro jogo.
- O gabarito é pequeno e parcialmente inferido (várias relações são deduções). Os clipes foram anotados com poucos quadros e depois ampliados onde o extrator achou algo, então a revocação em vídeo é um limite superior.
- O dicionário do estudo foi escrito à parte do gabarito, mas por quem o conhecia.
