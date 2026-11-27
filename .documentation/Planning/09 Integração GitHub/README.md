# 09 — Integração GitHub

Define o diferencial do produto: ligar um erro no log ao código que o causou e abrir uma issue.

Separado da área 04 porque envolve muito mais que IA: autenticação com o GitHub, vínculo entre container
e repositório, leitura de código, e a ação de abrir issue.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Vínculo Container e Repositório](Vínculo%20Container%20e%20Repositório.md) | Pré-preenchimento OCI, validação de repositório de código, qual commit usar, redeploy | Rascunho para revisão |
| [Autenticação](Autenticação.md) | Registro do App, permissões, tokens, múltiplas instalações, falhas | Rascunho para revisão |
| [Leitura de Código](Leitura%20de%20Código.md) | Pistas sem IA, seleção de arquivos em ordem, cache, limites | Rascunho para revisão |
| [Diagnóstico de Código](Diagnóstico%20de%20Código.md) | Fluxo IA-2, esquema, regras do prompt, interface | Rascunho para revisão |
| [Abertura de Issues](Abertura%20de%20Issues.md) | Quando, deduplicação com reabertura, template, labels, rastreabilidade, falhas | Rascunho para revisão |
| [Limites e Custos](Limites%20e%20Custos.md) | Limites da API do GitHub, tokens, custo por erro, privacidade | Rascunho para revisão |

## Decisões já tomadas

- **Autenticação por GitHub App**, nunca token pessoal. Ver [ADR 007](../02%20Arquitetura/ADR/ADR%20007%20Integração%20GitHub%20via%20GitHub%20App.md).
- **Fase:** a integração não entra na primeira fase de construção, e desde 2026-11-27 vem depois do servidor MCP, nas fases 1.3.0 a 1.5.0. Chega quando o Lognix passar a localizar o problema no código e abrir issues. Até lá o produto funciona só com log.
- **Vínculo é responsabilidade do usuário.** Ele associa cada workload a um repositório pela interface. O Lognix tenta pré-preencher lendo as labels OCI da imagem, `org.opencontainers.image.source` e `org.opencontainers.image.revision`, quando existirem.
- **Workload sem repositório é "somente imagem".** O Lognix o trata como uma imagem Docker: analisa logs e eventos, gera insights, mas não faz diagnóstico de código nem abre issue.
- **Só repositórios de código.** O repositório vinculado tem que ser o codebase do sistema que roda no container. Repositórios de infraestrutura, manifests ou GitOps não são aceitos como vínculo.
- **Uma issue por combinação workload e padrão de erro.** Em recorrência, o Lognix comenta na issue existente com contagem e horário. Se a issue foi fechada e o erro voltou, o Lognix a **reabre**: isso sinaliza que o problema não foi resolvido. Abrir, comentar e reabrir issues de erro é responsabilidade do Lognix, não do usuário.
