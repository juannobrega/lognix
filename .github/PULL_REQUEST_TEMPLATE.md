## O que muda

<!-- Uma ou duas frases. O que o usuário vai notar de diferente. -->

## Por quê

<!-- O problema que isso resolve. Se há uma issue, referencie com "Resolve #N". -->

## Como verifiquei

<!-- O que você rodou e o que viu. Testes automatizados e verificação manual, se houve. -->

- [ ] `ruff check`, `mypy` e `pytest` no backend
- [ ] `lint`, `typecheck`, `test` e `build` no frontend
- [ ] Verificado na stack real com `docker compose up`

## Documentação

- [ ] O documento da área em `.documentation/Planning` reflete a mudança
- [ ] Decisão não óbvia virou ADR
- [ ] `.documentation/Software` atualizado, se a mudança afeta quem instala ou opera

## Label de release

Este PR precisa de **exatamente uma**: `release:major`, `release:minor`, `release:patch` ou
`release:skip`. Sem label, o workflow de release falha de propósito.
