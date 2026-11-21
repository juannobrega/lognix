# Telas Detalhadas

**Status:** Aprovado em 2026-11-21 (telas da 0.4.0) · **Atualizado:** 2026-11-21

Wireframe textual e comportamento das telas principais. Rotas e fases em [Mapa de Telas](Mapa%20de%20Telas.md).

## Painel `/`

```
┌ barra lateral ┬──────────────────────────────────────────────────────────┐
│ Painel        │ Hosts: 3 conectados · 1 desconectado        IA: ativa     │
│ Hosts         ├───────────────────────────┬──────────────────────────────┤
│ Projetos      │ INSIGHTS NOVOS (7)        │ NOTIFICAÇÕES (3)             │
│ Insights  7   │ ● critical  api  3 min    │ ● novo container worker-2    │
│ Notif.    3   │ ● high      db   12 min   │   [monitorar] [ignorar]      │
│ Config.       │ ● medium    api  1 h      │ ● host vm-02 desconectado    │
│               │ ...                       │   [reconectar]               │
│               │ [ver todos] [limpar todos]│ [ver todas] [limpar todas]   │
│               ├───────────────────────────┴──────────────────────────────┤
│               │ EXECUTOR: api · trigger erro · aguardando IA · 00:12     │
│               ├──────────────────────────────────────────────────────────┤
│ v0.8.0        │ HOJE: 42 ciclos com trigger · 9 chamadas de IA · $0.31   │
│ juan          │ PROJETOS: 12 monitorados · 2 com erro na última hora     │
└───────────────┴──────────────────────────────────────────────────────────┘
```

- Insights ordenados por severidade e depois por horário. Clique abre o Insight.
- Notificações com ação direta inline.
- Sem IA configurada: o bloco de insights vira um aviso com link para Configurações › IA.
- Sem hosts: a tela inteira vira o estado vazio "cadastre o primeiro host".

## Cadastrar host `/hosts/new`

Passo 1, formulário: nome, endereço, porta, usuário, método de autenticação com campos condicionais.
Aviso ao escolher senha. Botão "Conectar".

Passo 2, validação ao vivo, por WebSocket `validation:{id}`:

```
✔ 1. Alcançar vm-01:22
✔ 2. Autenticar como deploy
✔ 3. Fingerprint SHA256:ab12...  [registrado]
✔ 4. Encaminhar docker.sock
✘ 5. Falar com o Docker
     O usuário deploy não tem acesso ao Docker.
     No host: sudo usermod -aG docker deploy && newgrp docker
     [tentar de novo]
○ 6. Listar containers
```

Passo 3, seleção: lista de containers com nome, imagem, estado, projeto Compose. Checkbox por
container e "selecionar todos do projeto X". Aviso fixo: "a coleta começa agora, logs anteriores não
serão coletados". Botão "Monitorar selecionados".

## Host `/hosts/:id`

Cabeçalho: nome, endereço, estado do túnel com tempo conectado, versão do Docker, botões reconectar e
remover. Abas:

- **Containers:** inventário com toggle de monitorado por linha. Mudança recarrega Alloy e mostra
  "config aplicada" ou erro.
- **Excluídos:** containers que sumiram, com data, e link para seus insights.
- **Eventos:** HostEvent em linha do tempo.
- **Config do Alloy:** bloco gerado para este host, versões, hash, motivo, resultado do reload.
- **Conexão:** credenciais mascaradas, fingerprint, editar.

## Projeto `/projects/:id`

Cabeçalho: nome, host, imagem com digest curto, estado, tipo `imagem` ou `github`, restarts na última
hora, botão "analisar agora" com seletor de janela. Abas:

- **Logs:** ver abaixo.
- **Insights:** lista do projeto, novos e histórico.
- **Padrões:** tabela de templates com contagem, nível, primeira e última vez, amostra. Clique filtra os logs pelo padrão.
- **Eventos:** DockerEvent, incluindo redeploy com imagem anterior e nova.
- **Repositório:** fase 1.1. Antes disso mostra "disponível em breve" e as labels OCI lidas da imagem.

## Logs do projeto `/projects/:id/logs`

```
[ ao vivo ● ] [ histórico ]   período: [últimos 15 min ▾]   nível: [todos ▾]   stream: [ambos ▾]
🔍 filtrar texto________________________                      [⏸ pausar] [↓ fim]
──────────────────────────────────────────────────────────────────────────────
14:02:11.123  stderr  ERROR  Connection refused: db:5432
14:02:11.124  stderr         Traceback (most recent call last):
14:02:11.125  stderr           File "app/db.py", line 42, in connect
...
```

- Linhas de erro com destaque. Clique em uma linha mostra labels e copia permalink com timestamp.
- Ao vivo: autoscroll, pausa ao rolar para cima, botão para voltar ao fim. Contador de linhas novas enquanto pausado.
- Histórico: paginação infinita para cima e para baixo. Permite abrir um insight e ver suas evidências marcadas no log.
- Estado vazio após marcação: "Monitorando desde 14:00. Aguardando as primeiras linhas." com indicador animado.
- Fonte monoespaçada, virtualização de lista obrigatória.

## Insight `/insights/:id`

```
● CRITICAL   api · vm-01                    confiança 0,82   [marcar visto]
Falha de conexão com o banco após redeploy
trigger: erro · 14:02 · ciclo 14:01:40 → 14:02:15

RESUMO        ...
CAUSA PROVÁVEL ...
AÇÃO SUGERIDA  ...

EVIDÊNCIAS
  [log] 14:02:11 ERROR Connection refused: db:5432          → ver no log
  [evento] 13:58 redeploy  api:1.4.0 → api:1.5.0
  [padrão] "Connection refused: <*>"  × 37

DIAGNÓSTICO DE CÓDIGO   (fase 1.2)
CHAMADA DE IA   modelo · 7 812 in · 540 out · $0.03 · 6,2 s · prompt v3   [ver contexto enviado]
```

"Ver contexto enviado" abre o texto exato que foi para o OpenRouter. Transparência, Guardrails seção 1.

## Configurações › IA `/settings/ai`

Aviso fixo de dados sensíveis no topo. Toggle ativar. Chave com "testar" e resultado inline. Seletor
de modelo com busca e preços. Limites: tokens de entrada, saída, concorrência. Botão salvar. Estado
atual: ativa desde, modelo, última chamada.
