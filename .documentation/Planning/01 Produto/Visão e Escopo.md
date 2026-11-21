# Visão e Escopo

**Status:** Em revisão · **Atualizado:** 2026-11-21

## 1. O que é o Lognix

Lognix é um software **de código aberto** que monitora e armazena logs de containers Docker rodando em
hosts remotos e usa IA para explicar o que aconteceu. Quando detecta um erro, vai além do log: olha o
**código do projeto no GitHub** para localizar onde está o problema e abre uma **issue** com o diagnóstico.

Será publicado como projeto aberto e divulgado pelo autor no LinkedIn. Isso impõe dois requisitos ao
produto: ser **instalável por qualquer pessoa com um `docker compose up`** e ter um **diferencial claro**,
que é o diagnóstico de causa raiz ligado ao código-fonte.

## 2. Problema

Equipes que operam serviços em containers têm logs espalhados por vários hosts e dependem de `docker logs`,
`grep` e intuição para entender incidentes. Ferramentas de observabilidade mostram os logs, mas não os
**explicam**, e nenhuma conecta o erro ao trecho de código que o causou.

## 3. Proposta

1. **Coleta sem agente no host.** O Lognix se conecta por SSH aos hosts cadastrados e, por um túnel, lê
   os logs via Docker API. O Grafana Alloy roda **ao lado do Lognix**, não no host monitorado.
   Nada é instalado na máquina observada. Ver [ADR 002](../02%20Arquitetura/ADR/ADR%20002%20Coleta%20Remota%20via%20Túnel%20SSH.md).
2. **Armazenamento central no Loki.** Toda linha de log fica no Loki com labels de host e container.
   Ver [ADR 001](../02%20Arquitetura/ADR/ADR%20001%20Loki%20como%20Armazenamento%20de%20Logs.md).
3. **Somente leitura, garantido.** O Lognix nunca altera nada no Docker de um host monitorado. Isso é
   imposto por um proxy no próprio Lognix, não só prometido. Ver [ADR 003](../02%20Arquitetura/ADR/ADR%20003%20Proxy%20Somente%20Leitura%20para%20Docker%20API.md).
4. **Rotina de análise a cada 30 segundos.** O backend consulta o Loki pela janela recente dos containers
   selecionados, agrupa padrões, detecta erros e anomalias e dispara a IA quando necessário.
   Ver [ADR 005](../02%20Arquitetura/ADR/ADR%20005%20Ciclo%20de%20Análise%20e%20Visualização%20ao%20Vivo.md).
5. **Visualização ao vivo.** A interface permite acompanhar logs em tempo real quando o usuário quiser.
6. **IA que explica e aponta o código.** Resumo do que aconteceu, causa provável, e, para projetos ligados
   a um repositório GitHub, o arquivo e trecho suspeitos. Ver [04 Inteligência Artificial](../04%20Inteligência%20Artificial/README.md)
   e [09 Integração GitHub](../09%20Integração%20GitHub/README.md).
7. **Ação: abrir issue no GitHub.** Única ação externa da v1, via GitHub App. Em recorrência comenta, se
   fechada e o erro voltou, reabre. Alertas por outros canais ficam no [Roadmap](../08%20Gestão/Roadmap.md).
8. **IA acionada por triggers.** Nunca roda sozinha. Erro na janela dispara coleta de contexto, prompt e
   insight. Provider único na v1: OpenRouter, configurado na interface, com custo e chamadas contabilizados.
9. **Login e usuários.** Tela de login com JWT e cadastro de usuários. Sem papéis.

## 3.1 Fluxo principal

1. O usuário cadastra uma **máquina**: endereço, porta, usuário SSH e chave.
2. O Lognix testa a conexão SSH, abre o túnel e verifica que há Docker respondendo. Se falhar, mostra o motivo.
3. O Lognix lista os **containers disponíveis** na máquina. O usuário seleciona quais quer **monitorar**.
4. Só os selecionados passam a ter logs coletados e analisados. Cada container monitorado é um **projeto**.
5. Opcionalmente, o usuário vincula o projeto a um **repositório GitHub** de código. Sem vínculo, o projeto é do tipo imagem Docker.
6. Se um **container novo** aparece na máquina, o Lognix emite uma notificação. O usuário escolhe se passa a monitorá-lo.
7. A rotina de 30 s gera **insights**. Eles ficam na tela até o usuário marcar como vistos, individualmente ou com "limpar todos".

## 4. Objetivos (v1)

| ID | Objetivo | Como medir |
|----|----------|-----------|
| O1 | Cadastrar um host por SSH e ver seus containers e logs em menos de 5 minutos | Tempo de onboarding em máquina limpa |
| O2 | Coleta contínua e sem perda de logs de todos os containers selecionados | Teste de 1 h com 50 containers, 0 linhas perdidas |
| O3 | Rotina de análise completa em menos de 30 s para a janela de 30 s | p95 do tempo de execução da rotina |
| O4 | Agrupamento de padrões reduz linhas exibidas em pelo menos 90% | Razão linhas brutas / padrões |
| O5 | Diagnóstico de erro aponta arquivo e trecho corretos no repositório | Avaliação manual em projetos de teste |
| O6 | Issue aberta no GitHub com contexto suficiente para um dev agir sem abrir o Lognix | Revisão manual das issues geradas |
| O7 | Subir o Lognix inteiro com um `docker compose up` em qualquer máquina com Docker | Reprodutível em máquina limpa |
| O8 | Host monitorado permanece intocado e nunca recebe comando de alteração | Teste automatizado contra o proxy somente leitura |
| O9 | Todo gasto com IA é visível: chamadas, tokens e custo por período, host e workload | Reconciliação com o painel do OpenRouter |

## 5. Não-objetivos (v1)

- **Não** instala nada no host monitorado. Nem agente, nem proxy, nem alteração de configuração do Docker.
- **Não** altera nada no Docker remoto. Não reinicia, não para, não remove.
- **Não** suporta Kubernetes. Fica para a v2, mas as abstrações não podem assumir Docker.
- **Não** tem permissionamento. Há login e vários usuários, mas todos com acesso total. RBAC está no roadmap.
- **Não** é multi-tenant. Uma instalação, um conjunto de hosts.
- **Não** notifica por Slack, e-mail ou webhook. Só abre issue no GitHub.
- **Não** suporta outro provider de IA além do OpenRouter.
- **Não** faz diagnóstico de código para workload sem repositório vinculado. Esse workload é tratado como somente imagem.
- **Não** aceita repositórios de infraestrutura ou GitOps como vínculo. Só o codebase do sistema.
- **Não** faz APM, tracing distribuído ou dashboards genéricos.
- **Não** indexa texto completo. Busca é por labels e janela de tempo, como o Loki trabalha.

## 6. Personas

| Persona | Necessidade principal |
|---------|------------------------|
| **Dono do projeto / dev solo** | Cadastrar suas VMs, ver o que está acontecendo, receber issues quando algo quebra |
| **Dev de time pequeno** | Ler logs do seu serviço e perguntar "o que quebrou" sem acesso SSH ao host |
| **Quem avalia o projeto no GitHub** | Subir em 5 minutos, entender o diferencial, confiar que é somente leitura |

## 7. Princípios de produto

1. **Nada no host.** O único requisito é SSH com acesso ao socket Docker.
2. **Somente leitura.** Imposto por código, auditável, testado.
3. **Logs primeiro, IA depois.** A interface de logs tem que ser boa com IA desligada.
4. **IA explicável.** Toda saída de IA mostra as linhas e o trecho de código que a embasaram.
5. **Custo visível.** Cada chamada de IA registra tokens, custo e gatilho. O usuário vê consumo por período, host e workload.
6. **Alloy e Loki como estão.** Lognix não reimplementa coleta nem armazenamento. Gera config e consulta.
7. **Kubernetes-ready por desenho.** "Instância" e "workload" são abstrações neutras.
8. **Instalação trivial.** Um compose, um `.env` mínimo, pronto. Chaves de IA e GitHub são configuradas na interface, não no `.env`.

## 8. Divisão de responsabilidades

| Responsabilidade | Componente |
|---|---|
| Abrir e manter túneis SSH com os hosts | Backend Python |
| Impor somente leitura na Docker API | Proxy no backend |
| Descobrir containers e ler logs | Grafana Alloy, via túnel |
| Armazenar e consultar logs | Loki |
| Inventário, estado, eventos e inspeção de containers | Backend via Docker API no túnel |
| Rotina de análise a cada 30 s, triggers, IA, GitHub | Backend Python |
| Autenticação, usuários, configuração de providers | Backend Python |
| Interface, logs ao vivo, insights, issues | Frontend React |
