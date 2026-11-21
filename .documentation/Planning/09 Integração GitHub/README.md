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
