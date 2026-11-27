# Abertura de Issues

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21 · **Fase:** a seguir, 3 de 3

Única ação externa do Lognix. Abrir, comentar e reabrir é responsabilidade do Lognix.

## 1. Quando

Após IA-1, e IA-2 se houver, em projeto do tipo GitHub, quando a severidade for `medium` ou acima.
`low` e `info` não abrem issue. Limite configurável.

## 2. Deduplicação, decidida

Chave: `(container_id, pattern_id)` do padrão de erro principal do insight.

| Situação | Ação |
|---|---|
| Sem issue para a chave | abre issue nova |
| Issue aberta existe | comenta: horário, contagem de ocorrências desde o último comentário, link para o novo insight. Máximo 1 comentário por hora por issue |
| Issue fechada existe e o erro voltou | **reabre** e comenta "o erro voltou a ocorrer em ...". Incrementa `reopened_count` |

Reabrir sinaliza que o problema não foi resolvido. Se o usuário fechar como "não vai corrigir", pode
marcar o padrão como ignorado na aba Padrões do projeto; o Lognix para de abrir e reabrir para ele.
Campo `Pattern.ignored`, a adicionar ao Modelo de Dados.

## 3. Conteúdo

Título: gerado por IA-3, máximo 80 caracteres, prefixo `[lognix]`.

Corpo, template fixo com seções preenchidas pelo backend e uma pela IA:

```markdown
> Issue aberta automaticamente pelo Lognix a partir do insight <link>.

## O que aconteceu
<IA-3: resumo e causa provável, até 1 200 caracteres>

## Onde
<arquivo e linhas do diagnóstico, com permalink do GitHub no ref exato; ou "sem diagnóstico de código">

## Evidências
<linhas de log, até 20, em bloco de código, com timestamps; eventos Docker relevantes>

## Contexto
- Projeto: `api` em `vm-01`
- Imagem: `ghcr.io/x/api@sha256:...`
- Redeploy recente: `1.4.0 → 1.5.0` em 2026-11-21 13:58
- Trigger: erro · Severidade: high · Confiança: 0,82

---
<sub>Lognix v1.3.0 · não responda nesta issue para o Lognix, ele não lê comentários</sub>
```

Evidências e Contexto são montados pelo backend, nunca pela IA. Guardrails seção 6.

## 4. Labels e atribuição

Label `lognix` criada no repositório se não existir. Severidade como label `severity:high`. Sem
assignee na v1.

## 5. Rastreabilidade

`GithubIssue` guarda número, estado, contagem. O Insight mostra o link da issue. A issue tem link para
o insight, que exige login no Lognix.

## 6. Falhas

Falha ao abrir ou comentar vira notificação `github_error` com o motivo. O insight fica marcado
"issue pendente" e o Lognix tenta de novo no próximo insight da mesma chave, não em loop.
