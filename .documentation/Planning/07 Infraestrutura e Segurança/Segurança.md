# Segurança

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Consolida o que já está nos ADRs e adiciona o que falta.

## 1. Ativos a proteger

| Ativo | Onde | Proteção |
|---|---|---|
| Credenciais SSH dos hosts | Postgres, criptografadas | `LOGNIX_SECRET_KEY`, nunca em log, mascaradas na API |
| Chave do OpenRouter | Postgres, criptografada | idem |
| Chave privada do GitHub App | Postgres, criptografada | idem, fase 1.1 |
| Logs dos hosts | Loki | rede interna, sem porta exposta |
| Contexto enviado à IA | Postgres | só via API autenticada |
| Senhas dos usuários | Postgres | Argon2id |

## 2. Superfície de ataque

| Entrada | Mitigação |
|---|---|
| Porta do frontend, única exposta | login obrigatório, rate limit, cabeçalhos de segurança, CSP |
| WebSocket | token na abertura, fechado ao expirar |
| Hosts remotos comprometidos | o Lognix só lê. Um host malicioso pode enviar logs forjados, que são dados não confiáveis: escapados na interface, tratados como dado no prompt, Guardrails seção 6 |
| Fingerprint SSH | fixado no primeiro acesso, divergência bloqueia |
| Resposta do OpenRouter | validada por esquema, nunca executada |
| Dependências | Dependabot e `pip-audit` / `npm audit` no CI |

## 3. O que o Lognix garante ao host

- Nenhum comando de alteração: proxy somente leitura, lista de caminhos, teste obrigatório. ADR 003.
- Nenhum software instalado. ADR 002.
- Recomendações ao usuário na documentação: usuário SSH dedicado, chave em vez de senha, sem shell
  se possível, grupo `docker` e nada mais.

## 4. Criptografia em repouso

- Chave simétrica derivada de `LOGNIX_SECRET_KEY` por HKDF, com contextos distintos para campos e para JWT.
- Algoritmo autenticado, AES-GCM ou equivalente da biblioteca escolhida, com nonce por registro.
- Rotação de chave: roadmap. Na v1, trocar a chave exige recadastrar credenciais, e isso é documentado.

## 5. Dados que saem do ambiente

Só para o OpenRouter e, na fase GitHub, para o GitHub. Sem telemetria, sem chamadas a serviços do
autor, sem verificação de atualização automática. Isso é afirmado no README como compromisso.

## 6. Auditoria

Na v1, mínimo: toda requisição rejeitada pelo proxy somente leitura é registrada; toda chamada de IA
tem `AICall`; todo visto tem `seen_by`. Trilha de auditoria completa está no roadmap.

## 7. Processo

- Arquivo `SECURITY.md` no repositório com como reportar vulnerabilidade.
- `security-review` do CI em PRs que toquem `security/`, `hosts/tunnel/`, `readonly_proxy/`, `auth/`.
