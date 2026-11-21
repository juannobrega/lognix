# 09 — Integração GitHub

Define o diferencial do produto: ligar um erro no log ao código que o causou e abrir uma issue.

Separado da área 04 porque envolve muito mais que IA: autenticação com o GitHub, vínculo entre container
e repositório, leitura de código, e a ação de abrir issue.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| Vínculo Container e Repositório | Como o Lognix descobre qual repositório e commit um container está rodando: labels OCI na imagem, configuração manual, convenções | A criar |
| Autenticação | GitHub App vs. token pessoal, permissões mínimas, armazenamento da credencial | A criar |
| Leitura de Código | Como selecionar os arquivos relevantes a partir de um erro: stack trace, nome de módulo, busca no repositório, limites de tamanho | A criar |
| Diagnóstico de Código | Como a IA combina log, evento Docker e código para apontar arquivo e trecho, e como a saída é estruturada | A criar |
| Abertura de Issues | Template da issue, deduplicação, quando abrir e quando só comentar, rastreabilidade de volta ao Lognix | A criar |
| Limites e Custos | Tamanho máximo de código enviado à IA, cotas da API do GitHub, cache | A criar |

## Decisões já tomadas

- **Autenticação por GitHub App**, nunca token pessoal. Ver [ADR 007](../02%20Arquitetura/ADR/ADR%20007%20Integração%20GitHub%20via%20GitHub%20App.md).
- **Fase:** a integração não entra na primeira fase de construção. Chega quando o Lognix passar a localizar o problema no código e abrir issues. Até lá o produto funciona só com log.
- **Vínculo é responsabilidade do usuário.** Ele associa cada workload a um repositório pela interface. O Lognix tenta pré-preencher lendo as labels OCI da imagem, `org.opencontainers.image.source` e `org.opencontainers.image.revision`, quando existirem.
- **Workload sem repositório é "somente imagem".** O Lognix o trata como uma imagem Docker: analisa logs e eventos, gera insights, mas não faz diagnóstico de código nem abre issue.
- **Só repositórios de código.** O repositório vinculado tem que ser o codebase do sistema que roda no container. Repositórios de infraestrutura, manifests ou GitOps não são aceitos como vínculo.
- **Uma issue por combinação workload e padrão de erro.** Em recorrência, o Lognix comenta na issue existente com contagem e horário. Se a issue foi fechada e o erro voltou, o Lognix a **reabre**: isso sinaliza que o problema não foi resolvido. Abrir, comentar e reabrir issues de erro é responsabilidade do Lognix, não do usuário.
