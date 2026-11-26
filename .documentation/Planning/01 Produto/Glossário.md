# Glossário

**Status:** Em revisão · **Atualizado:** 2026-11-21

| Termo | Definição no contexto do Lognix |
|-------|---------------------------------|
| **Instância** | Um host, tipicamente uma VM, com Docker rodando, alcançável por SSH. Abstração neutra: hoje Docker, amanhã nó Kubernetes. |
| **Workload** | Unidade monitorada dentro de uma instância. No Docker, um container. No Kubernetes, pod/container. |
| **Projeto** | Sinônimo de workload na interface. **Um projeto é um container.** Tem dois tipos: **imagem Docker**, sem repositório vinculado, e **GitHub**, com repositório de código vinculado. |
| **Monitorado** | Estado de um container selecionado pelo usuário. Só containers monitorados têm logs coletados pelo Alloy e passam pela rotina de análise. Os demais aparecem no inventário, mas nada é coletado. |
| **Notificação** | Aviso na interface sobre um fato que pede atenção do usuário, por exemplo container novo no host, túnel caído, falha na IA. Fica até ser marcada como vista. |
| **Container excluído** | Container que existia no host e desapareceu do Docker. Para de ser monitorado automaticamente, vai para aba própria e mantém insights e histórico. |
| **Visto** | Ação do usuário sobre um insight ou notificação. O item sai da tela principal e fica no histórico. "Limpar todos" marca todos como vistos de uma vez. |
| **Host monitorado** | Sinônimo de instância. A máquina que o Lognix observa e **nunca altera**. |
| **Máquina do Lognix** | Onde o Lognix roda: backend, frontend, Alloy, Loki e banco, todos em containers. Qualquer máquina com Docker. |
| **docker.sock** | Socket Unix em `/var/run/docker.sock` por onde o daemon Docker recebe todos os pedidos da Docker API. Existe um em cada máquina com Docker. Ter acesso a ele equivale a controlar o Docker daquela máquina. |
| **Docker API** | API HTTP exposta pelo daemon no `docker.sock`. Lista containers, lê logs, emite eventos, inspeciona imagens. |
| **Túnel SSH** | Conexão SSH mantida pelo backend que espelha o `docker.sock` do host remoto como um socket local em `/tunnels/<host>.sock`. Quem conecta no espelho fala com o Docker remoto. |
| **Proxy somente leitura** | Filtro no backend entre o túnel e seus consumidores que só deixa passar requisições `GET` à Docker API. Garante que nada é alterado no host. |
| **Supervisor de túneis** | Componente do backend que abre, vigia e reconecta túneis, e remove os de hosts excluídos. |
| **Alloy** | Grafana Alloy. Roda ao lado do Lognix, lê o socket espelhado de cada host, descobre containers e envia logs ao Loki. |
| **Config Alloy** | Arquivo `.alloy` gerado pelo backend com um bloco por host. Recarregado via `/-/reload` sem reiniciar. |
| **Loki** | Banco de logs do ecossistema Grafana. Indexa só labels, comprime o conteúdo. Única fonte de verdade dos logs. |
| **LogQL** | Linguagem de consulta do Loki. |
| **Label** | Par chave/valor indexado no Loki que identifica um stream, por exemplo `host`, `container`, `compose_project`. |
| **Stream** | Sequência de linhas de log com o mesmo conjunto de labels. |
| **Rotina de análise** | Ciclo sequencial por container monitorado: consulta no Loki a janela desde o ciclo anterior, agrupa padrões, detecta erros e anomalias, aciona IA se houver trigger e espera a resposta, grava, aguarda 30 s e recomeça. |
| **Ciclo** | Uma execução da rotina de análise para um container. Gera um `AnalysisRun`. |
| **Executor** | Painel da interface que mostra as análises em andamento, manuais e automáticas. |
| **Janela** | Intervalo de tempo de uma consulta ou análise. No ciclo automático, vai do fim da janela anterior até o início do ciclo atual. |
| **Visualização ao vivo** | Modo da interface que acompanha logs em tempo real via tail do Loki, fora do ciclo de 30 s. |
| **Padrão (template)** | Linha de log com partes variáveis substituídas por `<*>`. Ex.: `user <*> logged in from <*>`. |
| **Anomalia** | Desvio em volume, taxa de erro ou surgimento de padrão inédito. |
| **Insight** | Saída estruturada de IA: resumo, causa provável, ação sugerida, trecho de código suspeito, ligada às linhas que a embasaram. |
| **Diagnóstico de código** | Insight que aponta arquivo e trecho no repositório GitHub do projeto ligado ao container. |
| **Vínculo de repositório** | Associação entre um container/projeto e um repositório GitHub, com referência de commit ou branch. |
| **Provider de IA** | Serviço de modelo de linguagem atrás da interface interna `AiProvider`. Vários podem ser cadastrados, e a ordem entre eles é a cadeia de fallback. |
| **OpenRouter** | Serviço que expõe dezenas de modelos de vários fabricantes por uma única API. Único provider da v1. |
| **Trigger** | Condição programática avaliada pela rotina de análise que, quando verdadeira, aciona a IA. O primeiro é o trigger de erro. |
| **Chamada de IA** | Registro de cada requisição ao provider: horário, modelo, tokens, custo, trigger, workload e insight gerado. |
| **GitHub App** | Aplicativo registrado no GitHub e instalado pelo usuário nos repositórios. Forma única de autenticação do Lognix com o GitHub. |
| **Workload somente imagem** | Workload sem repositório vinculado. Recebe análise de log e insights, mas não diagnóstico de código nem issue. |
| **Perfil de conexão** | Credencial SSH e endereço para alcançar uma instância. |
