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

## O que foi observado
- **A GPU é usada:** o Ollama detecta a RX 7600 via ROCm (`gfx1102`) e roda os modelos **100% na GPU**, sem precisar do modo Vulkan.
- **qwen2.5:7b (quantizado Q4):** cerca de 4,5 GB de memória de vídeo.
- **qwen2.5:3b (quantizado Q4):** cerca de 2 GB.
- Com o 7B sobram uns 3,5 GB, o que deixa pouco espaço para o jogo rodar junto; o processamento assíncrono (depois da sessão) continua sendo a escolha certa.
- O instalador do Ollama atualiza o app sozinho e cria um atalho de inicialização do Windows; o servidor pode ser iniciado com `ollama serve`.
