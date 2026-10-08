# Hardware do projeto

| Item | Valor |
|---|---|
| CPU | AMD Ryzen 5 5500 |
| RAM | 16 GB |
| GPU | AMD Radeon RX 7600 |
| VRAM | 8 GB |
| Sistema operacional | Windows 11 64 bit |
| Espaço livre em disco | SSD 100GB |

## O que isso significa para o projeto
- **Ollama:** a documentação oficial lista a RX 7600 entre as GPUs AMD suportadas via ROCm (Linux e Windows, nas versões de ROCm indicadas lá) e há suporte adicional via Vulkan (`OLLAMA_VULKAN=1`). Fonte: https://docs.ollama.com/gpu
- **Limite de VRAM:** com 8 GB, a regra prática é rodar bem modelos pequenos (cerca de 7–8B parâmetros quantizados). Modelos maiores vão parcialmente para a RAM e ficam bem mais lentos.
- **Consequência para o estudo:** testar primeiro modelos pequenos com visão e modelos de texto pequenos; registrar para cada teste modelo, quantização, uso de VRAM e tempo. Esses números alimentam a avaliação de "requisitos de hardware".
- **Se a GPU não for usada:** conferir o log do Ollama; tentar a opção Vulkan antes de desistir da aceleração.

## Medido em 2026-10-08 (Ollama 0.40.1, Windows 11)
- **A GPU é usada:** o Ollama detecta a RX 7600 via ROCm (`gfx1102`) e roda os modelos **100% na GPU**, sem precisar do modo Vulkan.
- **qwen2.5:7b (Q4):** 4,42 GB de VRAM, 7,8 s por imagem na tarefa de extração (cerca de 1.500 tokens de entrada e 250 de saída por imagem).
- **qwen2.5:3b (Q4):** 2,01 GB de VRAM, 6,1 s por imagem.
- Sobra mais de 3 GB de VRAM com o 7B, o que deixa espaço para o jogo rodar junto só em parte; o processamento assíncrono (após a coleta) continua sendo a escolha certa.
- O instalador do Ollama atualiza o app sozinho e cria um atalho de inicialização do Windows; o servidor foi iniciado com `ollama serve`.
