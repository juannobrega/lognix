# Ferramentas do MCP

**Status:** Construído na 1.2.0 · **Atualizado:** 2026-11-27

Dez ferramentas. A régua para cada uma foi: **responde a uma pergunta que alguém faria em voz alta
sobre um serviço**. Ferramenta que só existe porque a tabela existe não entrou.

| Ferramenta | Escopo | Devolve |
|---|---|---|
| `lognix_listar_hosts` | leitura | Máquinas monitoradas e o estado da conexão com cada uma |
| `lognix_listar_projetos` | leitura | Containers acompanhados, com host, imagem e estado |
| `lognix_buscar_logs` | leitura | Linhas de um projeto numa janela, com filtro de texto |
| `lognix_listar_insights` | leitura | Problemas diagnosticados, filtráveis por severidade e projeto |
| `lognix_obter_insight` | leitura | Um insight inteiro: causa provável, ação sugerida, evidências |
| `lognix_listar_ocorrencias` | leitura | Detecções do ciclo, analisadas ou não |
| `lognix_listar_padroes` | leitura | Padrões de log de um projeto, com contagem |
| `lognix_analisar_agora` | análise | Dispara um ciclo de análise do projeto e devolve o que detectou |
| `lognix_consumo_ia` | admin | Custo e tokens por período e por provedor |
| `lognix_estado_do_sistema` | admin | Hosts conectados, ciclos nas últimas 24 h, fila sem análise |

## Decisões de desenho

- **A descrição da ferramenta importa tanto quanto o código.** É por ela que o modelo decide se
  aquela ferramenta responde à pergunta que ele tem na mão. Descrição vaga produz chamada errada ou
  nenhuma chamada. A de `lognix_listar_projetos` diz explicitamente "comece por aqui", porque é o
  que dá os nomes que as outras aceitam.
- **Projeto é aceito por nome ou por uuid.** O modelo quase sempre tem o nome do container, que foi
  o que o usuário falou. Exigir uuid obrigaria uma chamada a mais em toda conversa.
- **Erro de argumento volta como erro visível ao modelo, com a saída.** "Projeto 'x' não encontrado.
  Use `lognix_listar_projetos` para ver os nomes" conserta a próxima chamada; "erro interno" não.
- **Tetos fixos nas respostas.** 300 linhas de log e 100 itens de lista, por chamada. Resposta maior
  que isso não cabe no contexto de quem perguntou e custa tokens dos dois lados.
- **Janela máxima de 16 dias** nas buscas, acima da retenção padrão do Loki de 15.
- **`lognix_analisar_agora` compartilha o limite da interface** — uma por minuto por projeto. Entrar
  por outra porta não dá cota extra de análise: o limite mora no módulo que as duas usam.
- **A ocorrência volta com `analisada: false`** quando a IA ainda não processou a detecção, e a
  resposta diz isso em texto. Sem essa indicação o modelo conclui que não há diagnóstico, quando o
  que há é um diagnóstico a caminho.

## O que nenhuma ferramenta faz

- **Escrever.** Não cadastra host, não marca container, não altera insight, não muda configuração.
  `lognix_analisar_agora` é a única que produz efeito, e o efeito é o mesmo do botão da tela.
- **Tocar no host monitorado.** A garantia de somente leitura dos hosts é anterior e continua
  valendo: o MCP fala com o banco e com o Loki do Lognix, nunca com o Docker remoto.
- **Devolver credencial.** Nem chave de provedor, nem senha de SSH, nem variável de ambiente de
  container. `lognix_estado_do_sistema` devolve contagens, não configuração.
