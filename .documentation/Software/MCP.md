# Conectar uma IA ao Lognix

O Lognix atende o **Model Context Protocol**. Na prática: você pergunta ao Claude "o que está
acontecendo com a api?" e ele consulta o seu Lognix — inventário, logs, padrões, insights — para
responder, sem você abrir a interface.

Funciona com qualquer cliente compatível. Os exemplos usam o Claude Code e o Claude Desktop porque
são os mais comuns.

## 1. Ligue o servidor

Em **Inteligência Artificial › MCP**, o interruptor no alto da tela. Ele nasce **desligado**: um
endereço que serve log não deveria passar a responder porque alguém atualizou a versão.

Desligado, `/mcp` responde **503** a todo mundo, com chave ou sem — e as chaves continuam
guardadas, intactas. É o jeito de cortar todo o acesso MCP de uma vez, sem revogar uma por uma.

!!! tip "Pode ficar no `config.yaml`"

    `mcp.enabled: true` sobe a instalação com o servidor já ligado. Declarado no arquivo, o
    interruptor aparece na tela e não deixa editar — ver [Configuração](Configuração.md).

## 2. Crie uma chave

**Inteligência Artificial › MCP › Nova chave.** Dê um nome que diga de quem é a chave — é por ele que você vai
saber qual revogar — e marque as permissões.

| Permissão | Libera | Se a chave vazar |
|---|---|---|
| **Leitura** | hosts, projetos, logs, padrões, ocorrências, insights | quem tem a chave lê os logs dos seus projetos |
| **Análise** | disparar uma análise na hora | além de ler, gasta com o provedor de IA que você configurou |
| **Administração** | consumo da IA e estado do sistema | expõe custos e a topologia da instalação |

!!! warning "A chave aparece uma vez"

    O Lognix guarda só o hash dela. Não existe tela que mostre a chave de novo — se perder, crie
    outra e revogue a antiga.

Recomendação: **uma chave por cliente**, com o menor escopo que resolva. É o que permite cortar um
sem derrubar os outros.

## 3. Aponte o cliente

=== "Claude Code"

    O comando pronto está na própria tela, com o seu endereço:

    ```bash
    claude mcp add --transport http lognix https://lognix.suaempresa.com/mcp \
      --header "Authorization: Bearer lgxmcp_..."
    ```

=== "Claude Desktop"

    Em `claude_desktop_config.json`:

    ```json
    {
      "mcpServers": {
        "lognix": {
          "type": "http",
          "url": "https://lognix.suaempresa.com/mcp",
          "headers": {
            "Authorization": "Bearer lgxmcp_..."
          }
        }
      }
    }
    ```

O endereço é o seu `LOGNIX_PUBLIC_URL` com `/mcp` no fim. Se o cliente responder **421**, o endereço
pelo qual ele chega não é o configurado — veja [Hosts aceitos](#hosts-aceitos).

## 4. Pergunte

Algumas perguntas que funcionam direto:

- "Quais projetos o Lognix está monitorando?"
- "O que aconteceu com a api na última hora?"
- "Tem algum insight crítico aberto?"
- "Mostra as linhas de erro do checkout de hoje"
- "Analisa o worker agora e me diz o que achou"
- "Quanto a análise por IA custou esta semana?"

## O que a IA pode fazer

| Ferramenta | Permissão | Para quê |
|---|---|---|
| `lognix_listar_hosts` | Leitura | máquinas monitoradas e estado da conexão |
| `lognix_listar_projetos` | Leitura | containers acompanhados, com host e imagem |
| `lognix_buscar_logs` | Leitura | linhas de um projeto, com janela e filtro de texto |
| `lognix_listar_insights` | Leitura | problemas diagnosticados |
| `lognix_obter_insight` | Leitura | um insight com causa, ação sugerida e evidências |
| `lognix_listar_ocorrencias` | Leitura | detecções do ciclo, analisadas ou não |
| `lognix_listar_padroes` | Leitura | padrões de log de um projeto, com contagem |
| `lognix_analisar_agora` | Análise | roda um ciclo agora, uma vez por minuto por projeto |
| `lognix_consumo_ia` | Admin | custo e tokens por período e por provedor |
| `lognix_estado_do_sistema` | Admin | hosts conectados, ciclos nas 24 h, fila sem análise |

**Nenhuma delas escreve.** Não cadastra host, não marca container, não altera insight, não muda
configuração. `lognix_analisar_agora` é a única com efeito, e o efeito é o mesmo do botão "analisar
agora" da tela. Nos hosts monitorados nada muda — essa garantia é anterior ao MCP e continua
valendo.

**Nenhuma delas devolve credencial.** Chave de provedor, senha de SSH e variável de ambiente de
container não entram em resposta nenhuma.

## Acompanhar e revogar

A aba MCP mostra, por chave, as permissões, o último uso e o total de chamadas — e, abaixo, as
últimas chamadas com a chave que fez cada uma. É por essa lista que se descobre uma chave em uso
indevido.

- **Desativar** suspende a chave sem apagar o histórico. O cliente para de responder na hora.
- **Revogar** apaga a chave. O histórico de chamadas continua.
- **Editar permissões** vale para a próxima chamada, inclusive numa conexão já aberta.

## Privacidade

Criar uma chave MCP é uma decisão de privacidade, não só de integração. As linhas de log saem do
Lognix para o cliente de quem tem a chave, e dali para o modelo que aquele cliente usa — que pode
não ser o provedor que você configurou no Lognix.

A diferença em relação à análise automática é quem escolhe o destino: ali é a sua configuração,
aqui é quem detém a chave. Daí a recomendação de escopo mínimo e uma chave por cliente.

## Hosts aceitos

Por padrão o `/mcp` só aceita requisições cujo cabeçalho `Host` seja o do seu `LOGNIX_PUBLIC_URL`
(ou localhost) — é a proteção padrão do protocolo contra DNS rebinding. Quem publica o Lognix por
mais de um nome, atrás de proxy, declara os nomes:

```bash
LOGNIX_MCP_ALLOWED_HOSTS=lognix.suaempresa.com,lognix.interno:8080
```

`*` desliga a checagem. A autenticação por chave continua valendo nos dois casos.
