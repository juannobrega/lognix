# Glossário

**Status:** Em revisão · **Atualizado:** 2026-11-21

| Termo | Definição no contexto do Lognix |
|-------|---------------------------------|
| **Instância** | Um host, tipicamente uma VM, com Docker rodando, alcançável por SSH. Abstração neutra: hoje Docker, amanhã nó Kubernetes. |
| **Workload** | Unidade monitorada dentro de uma instância. No Docker, um container. No Kubernetes, pod/container. |
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
| **Rotina de análise** | Processo do backend que roda a cada 30 s: consulta a janela recente no Loki, agrupa padrões, detecta erros e anomalias, aciona IA e GitHub quando necessário. |
| **Janela** | Intervalo de tempo de uma consulta ou análise. A rotina padrão usa 30 s. |
| **Visualização ao vivo** | Modo da interface que acompanha logs em tempo real via tail do Loki, fora do ciclo de 30 s. |
| **Padrão (template)** | Linha de log com partes variáveis substituídas por `<*>`. Ex.: `user <*> logged in from <*>`. |
| **Anomalia** | Desvio em volume, taxa de erro ou surgimento de padrão inédito. |
| **Insight** | Saída estruturada de IA: resumo, causa provável, ação sugerida, trecho de código suspeito, ligada às linhas que a embasaram. |
| **Diagnóstico de código** | Insight que aponta arquivo e trecho no repositório GitHub do projeto ligado ao container. |
| **Vínculo de repositório** | Associação entre um container/projeto e um repositório GitHub, com referência de commit ou branch. |
| **Provider de IA** | Backend de modelo de linguagem: Anthropic, OpenAI-compatível, Ollama local. |
| **Perfil de conexão** | Credencial SSH e endereço para alcançar uma instância. |
