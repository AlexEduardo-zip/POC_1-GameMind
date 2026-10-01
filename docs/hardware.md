# Hardware do projeto

| Item | Valor |
|---|---|
| CPU | AMD Ryzen 5 5500 |
| RAM | 16 GB |
| GPU | AMD Radeon RX 7600 |
| VRAM | 8 GB (valor padrão da placa; confirmar no Gerenciador de Tarefas > Desempenho > GPU > "Memória dedicada") |
| Sistema operacional | (preencher) |
| Espaço livre em disco | (preencher) |

## O que isso significa para o projeto
- **Ollama:** a documentação oficial lista a RX 7600 entre as GPUs AMD suportadas via ROCm (Linux e Windows, nas versões de ROCm indicadas lá) e há suporte adicional via Vulkan (`OLLAMA_VULKAN=1`). Fonte: https://docs.ollama.com/gpu
- **Limite de VRAM:** com 8 GB, a regra prática é rodar bem modelos pequenos (cerca de 7–8B parâmetros quantizados). Modelos maiores vão parcialmente para a RAM e ficam bem mais lentos.
- **Consequência para o estudo:** testar primeiro modelos pequenos com visão e modelos de texto pequenos; registrar para cada teste modelo, quantização, uso de VRAM e tempo. Esses números alimentam a avaliação de "requisitos de hardware".
- **Se a GPU não for usada:** conferir o log do Ollama; tentar a opção Vulkan antes de desistir da aceleração.
