# Requisitos Funcionais

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Lista numerada do que o sistema faz. Cada requisito aponta a fase em que entra e o documento que o detalha.

## Acesso
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-001 | Criar o primeiro usuário em sistema vazio | 0.1.0 | Autenticação e Autorização |
| RF-002 | Login com e-mail e senha, sessão por JWT com refresh | 0.1.0 | idem |
| RF-003 | Cadastrar, listar e remover usuários; trocar a própria senha | 0.1.0 | idem |

## Hosts
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-010 | Cadastrar host com nome, endereço, porta, usuário e autenticação SSH por chave, chave com passphrase ou senha | 0.2.0 | Inventário e Conexão |
| RF-011 | Validar a conexão em etapas visíveis, com mensagem e ação sugerida em cada falha | 0.2.0 | idem |
| RF-012 | Fixar o fingerprint SSH do host e bloquear divergência até aceite explícito | 0.2.0 | idem |
| RF-013 | Manter túnel SSH por host, reconectar automaticamente, notificar queda e retorno | 0.2.0 | idem |
| RF-014 | Garantir que nenhuma requisição de alteração chegue à Docker API do host | 0.2.0 | ADR 003 |
| RF-015 | Listar containers do host com estado, imagem e projeto Compose | 0.2.0 | Monitoramento Docker |
| RF-016 | Remover host ocultando-o e preservando dados; apagar de fato em operação separada com confirmação | 0.2.0 | Inventário e Conexão |

## Monitoramento
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-020 | Selecionar por host quais containers são monitorados | 0.3.0 | Grafana Alloy |
| RF-021 | Coletar logs só dos monitorados, a partir da marcação, via Alloy para o Loki | 0.3.0 | idem |
| RF-022 | Gerar, versionar e recarregar a config do Alloy a cada mudança, com reversão em falha | 0.3.0 | idem |
| RF-023 | Exibir logs históricos de um projeto com filtros de período, texto, nível e stream | 0.4.0 | Telas Detalhadas |
| RF-024 | Exibir logs ao vivo com pausa e retorno ao fim | 0.4.0 | idem |
| RF-025 | Reconciliar inventário periodicamente e por eventos; notificar container novo com ação de monitorar | 0.5.0 | Monitoramento Docker |
| RF-026 | Mover container desaparecido para Excluídos, preservando insights | 0.5.0 | idem |
| RF-027 | Reconhecer redeploy por identidade de serviço e manter o projeto | 0.5.0 | idem |
| RF-028 | Registrar eventos Docker dos monitorados: die, oom, restart, health, redeploy | 0.5.0 | idem |

## Análise
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-030 | Executar um ciclo de análise por container com 30 s entre o fim de um e o início do próximo | 0.6.0 | ADR 005 |
| RF-031 | Agrupar linhas em padrões e exibi-los com contagem | 0.6.0 | Pipeline |
| RF-032 | Classificar linhas como erro por nível estruturado ou regex | 0.6.0 | idem |
| RF-033 | Disparar triggers de erro, evento crítico, anomalia e manual | 0.6.0 | idem |
| RF-034 | Registrar triggers sem IA como ocorrências sem análise | 0.6.0 | Guardrails |
| RF-035 | Exibir o executor com análises em andamento | 0.6.0 | Pipeline |

## IA
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-040 | Configurar OpenRouter pela interface: chave, teste, modelo, limites, ativar | 0.9.0 | Providers |
| RF-041 | Montar contexto limitado por tokens e chamar a IA quando um trigger disparar | 0.9.0 | Pipeline |
| RF-042 | Validar a resposta contra esquema fechado, com um retry, e falhar com notificação | 0.9.0 | idem |
| RF-043 | Gravar insight com severidade, resumo, causa, ação, evidências, confiança e contexto enviado | 0.9.0 | idem |
| RF-044 | Marcar insight como visto, individualmente e em lote; manter histórico | 0.8.0 | Frontend |
| RF-045 | Registrar toda chamada de IA com tokens e custo; exibir consumo por período, host, projeto, trigger | 0.9.0 | Custos e Limites |
| RF-046 | Exibir aviso de dados sensíveis na configuração de IA | 0.9.0 | Guardrails |

## GitHub
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-050 | Configurar GitHub App pela interface | a seguir | Autenticação GitHub |
| RF-051 | Vincular projeto a repositório de código, com pré-preenchimento OCI e validação | a seguir | Vínculo |
| RF-052 | Selecionar e ler arquivos relevantes a partir do erro | a seguir | Leitura de Código |
| RF-053 | Produzir diagnóstico de código com arquivo, linhas e explicação | a seguir | Diagnóstico |
| RF-054 | Abrir, comentar e reabrir issues com deduplicação por projeto e padrão | a seguir | Issues |

## Servidor MCP
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-055 | Atender o Model Context Protocol em `/mcp`, com transporte HTTP | 1.2.0 | [Ferramentas](../10%20Servidor%20MCP/Ferramentas.md) |
| RF-056 | Expor hosts, projetos, logs, padrões, ocorrências e insights como ferramentas | 1.2.0 | Ferramentas |
| RF-057 | Disparar análise de um projeto por ferramenta, com o limite da interface | 1.2.0 | Ferramentas |
| RF-058 | Criar, listar, desativar e revogar chaves de API com escopo e validade | 1.2.0 | [Chaves e Permissões](../10%20Servidor%20MCP/Chaves%20e%20Permissões.md) |
| RF-059 | Mostrar a chave uma única vez, guardando só o hash | 1.2.0 | Chaves e Permissões |
| RF-070 | Registrar toda chamada MCP com chave, ferramenta, duração e erro | 1.2.0 | Chaves e Permissões |

## Sistema
| ID | Requisito | Fase | Ref |
|---|---|---|---|
| RF-060 | Notificações com visto e limpar todos, com ações inline | 0.5.0 | Frontend |
| RF-061 | Tela Sistema com versão, estado de componentes e loops | 0.7.0 | Observabilidade |
| RF-062 | Subir tudo com `docker compose up` e um `.env` mínimo | 0.1.0 | Ambientes |
