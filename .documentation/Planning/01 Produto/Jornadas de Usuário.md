# Jornadas de Usuário

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Fluxos ponta a ponta, do ponto de vista de quem usa. Servem para validar que telas, API e backend se
encaixam.

## J1. Primeira instalação até o primeiro log

1. Clona o repositório, copia `.env.example`, gera a chave, `docker compose up -d`.
2. Abre a interface. Vê a tela de criar o primeiro usuário. Cria.
3. Painel vazio com "cadastre o primeiro host". Clica.
4. Preenche nome, endereço, usuário, cola a chave. Conectar.
5. Vê as seis etapas avançando. A quinta falha: sem acesso ao Docker. Lê a instrução, executa no host, tenta de novo. Passa.
6. Vê a lista de containers. Marca três. Lê o aviso de que a coleta começa agora. Confirma.
7. Vai ao projeto `api`, aba Logs. Vê "monitorando desde agora, aguardando". Em segundos aparecem linhas.

Critério: menos de 10 minutos. Pontos de falha prováveis: chave em formato inesperado, permissão no
socket, firewall. Todos com mensagem e ação.

## J2. Um erro acontece

1. O container `api` começa a falhar ao conectar no banco.
2. No ciclo seguinte, o classificador encontra linhas de erro. Trigger de erro dispara.
3. O executor mostra "api · erro · aguardando IA". Em alguns segundos, um insight `high` aparece no painel e o contador da barra sobe.
4. O usuário abre o insight: resumo, causa provável "banco inacessível após redeploy", evidências com link para as linhas. Clica em uma evidência, cai no log histórico com a linha destacada.
5. Resolve o problema. O erro para. Marca o insight como visto.

Se a IA estiver desligada, o passo 3 vira uma ocorrência sem análise, e a tela diz isso.

## J3. Deploy de uma nova versão

1. `docker compose up -d` no host recria o `api`.
2. O Lognix recebe `destroy` e `start`. Reconhece pela identidade de serviço. Mantém o projeto, registra `redeploy 1.4.0 → 1.5.0`.
3. Nenhuma notificação de container novo. A aba Eventos mostra o redeploy.
4. Se um erro aparecer nos minutos seguintes, o insight cita o redeploy como contexto.

## J4. Um container novo aparece

1. Alguém sobe `worker-2` no host.
2. Notificação "novo container worker-2 em vm-01" com botões monitorar e ignorar.
3. Monitorar: Alloy recarregado, projeto criado, coleta começa.
4. Ignorar: notificação vista, container fica no inventário como não monitorado. Pode ser marcado depois na aba Containers do host.

## J5. O host cai

1. Túnel cai. Notificação "vm-01 desconectado". Lista de hosts mostra o estado.
2. Supervisor tenta reconectar com backoff. Projetos do host mostram "host desconectado" na aba Logs.
3. Host volta. Notificação "vm-01 reconectado". Coleta retoma. Os logs do período offline **não** são recuperados: o Alloy lê a partir da reconexão. Isso é dito na notificação.

## J6. Configurar a IA

1. Configurações › IA. Lê o aviso de dados sensíveis.
2. Cola a chave do OpenRouter, clica testar. Vê modelo, latência, custo da chamada de teste.
3. Escolhe o modelo pela lista com preços. Salva. Ativa.
4. Triggers já registrados como ocorrências sem análise não são reprocessados. Novos triggers passam a gerar insights.

## J7. Ligar um projeto ao GitHub, fase 1.1

1. Configurações › GitHub. Segue o passo a passo para criar o App, cola App ID e chave. Instala o App no repositório.
2. Projeto `api`, aba Repositório. Vê `owner/repo` sugerido pela label OCI. Confirma. Validação: App instalado, repositório de código, ref existe.
3. Próximo erro: o insight ganha a seção de diagnóstico de código e uma issue é aberta. O link da issue aparece no insight.
4. Erro persiste: a issue recebe um comentário por hora. Corrige e fecha. Erro volta uma semana depois: a issue é reaberta.
