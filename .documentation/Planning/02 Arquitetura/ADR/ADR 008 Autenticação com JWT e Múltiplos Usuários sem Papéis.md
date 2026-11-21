# ADR 008 — Autenticação com JWT e Múltiplos Usuários sem Papéis

**Status:** Aceito, aprovado para construção em 2026-11-21 · **Data:** 2026-11-21

## Contexto

O Lognix guarda credenciais SSH de hosts e chaves de API. Não pode ficar aberto a quem alcançar a
porta. Ao mesmo tempo, a v1 não tem permissionamento: todo usuário autenticado vê e faz tudo.

## Decisão

- Tela de login básica com usuário e senha. O backend devolve um **JWT**.
- **Cadastro de usuários** pela interface. O primeiro usuário é criado no primeiro acesso ao sistema
  vazio e passa a poder cadastrar os demais.
- **Sem papéis.** Todo usuário autenticado tem acesso total. RBAC fica no roadmap.
- Senhas com hash forte. JWT de curta duração com refresh.

## Alternativas consideradas

- **Sem login.** Inaceitável pela exposição de credenciais SSH.
- **Usuário único no `.env`.** Simples, mas não permite saber quem fez o quê, e dificulta a
  evolução para papéis.
- **OAuth externo na v1.** Roadmap.

## Consequências

- Entidade `User` entra no modelo de dados desde o início.
- Toda ação relevante pode ser atribuída a um usuário, preparando auditoria futura.
- Adicionar papéis depois é adicionar um campo e checagens, sem mudar a autenticação.
