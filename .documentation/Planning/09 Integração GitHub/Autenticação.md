# Autenticação com GitHub

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21 · **Fase:** 1.1.0

Base: ADR 007. GitHub App, nunca token pessoal.

## 1. Registro do App

Quem instala o Lognix cria um GitHub App na própria conta ou organização. A documentação em `Software/`
guia passo a passo, e a tela Configurações › GitHub mostra os valores exatos a preencher no GitHub:

| Campo no GitHub | Valor |
|---|---|
| Homepage URL | `LOGNIX_PUBLIC_URL` |
| Webhook | desativado na v1 |
| Permissões de repositório | Contents: read · Issues: read and write · Metadata: read |
| Onde instalar | só nesta conta |

Depois, o usuário informa no Lognix: `App ID`, chave privada `.pem`, e instala o App nos
repositórios desejados. O `Installation ID` é descoberto pelo Lognix listando as instalações do App.

## 2. Tokens

- JWT do App assinado com a chave privada, válido 10 min, usado só para obter tokens de instalação.
- Token de instalação válido 1 h, cacheado em memória, renovado 5 min antes de expirar.
- Nenhum token é persistido. Só a chave privada, criptografada em `Setting`.

## 3. Múltiplas instalações

Um App pode estar instalado em várias contas. `RepositoryLink.installation_id` guarda qual instalação
cobre cada repositório. A lista de repositórios acessíveis é obtida por instalação.

## 4. Falhas

| Falha | Comportamento |
|---|---|
| Chave inválida | teste na tela falha com mensagem; GitHub desativado |
| App não instalado no repo | vínculo recusado com link de instalação |
| Permissão insuficiente | notificação `github_error` com a permissão faltante |
| Rate limit | respeita cabeçalhos, adia a operação, notifica se persistir |
