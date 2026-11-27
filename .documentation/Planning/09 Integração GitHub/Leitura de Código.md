# Leitura de Código

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21 · **Fase:** a seguir, 2 de 3

Como escolher o que enviar à IA a partir de um erro. Repositórios inteiros não cabem no prompt.

## 1. Entrada

Insight de IA-1 com `needs_code = true`, as linhas de erro, e o ref a usar.

## 2. Pistas extraídas das linhas de erro, sem IA

| Pista | Regex ou regra | Exemplo |
|---|---|---|
| Caminho e linha em stack trace | padrões por linguagem: Python `File "x.py", line N`, Node `at fn (x.js:N:M)`, Go `x.go:N`, Java `at pkg.Class.method(Class.java:N)` | `app/db.py:42` |
| Nome de módulo, classe ou função | tokens em `CamelCase` ou `snake_case` próximos a `Error`, `Exception`, `in` | `connect`, `DatabaseError` |
| Mensagem de erro literal | a parte textual da linha de erro | `Connection refused` |
| Variável de ambiente ou config | `[A-Z_]{4,}` | `DATABASE_URL` |

## 3. Seleção de arquivos

Ordem, parando quando o orçamento de tokens de código, padrão 20 000, estiver cheio:

1. **Arquivos citados em stack trace**, com janela de ±60 linhas ao redor de cada linha citada.
   Caminhos de dentro do container são normalizados removendo prefixos como `/app/`, `/usr/src/app/`,
   `/srv/`. Se o arquivo não existir no ref, tenta busca por nome de arquivo no repositório.
2. **Busca por código** na API do GitHub com as mensagens literais e os nomes de função. Até 5 arquivos,
   janela ao redor das ocorrências.
3. **Arquivos de configuração** quando a pista é variável de ambiente: `docker-compose*.yml`,
   `Dockerfile`, `.env.example`, `config/*`.
4. Se nada foi encontrado: envia a árvore de diretórios até 2 níveis e pede à IA que indique os arquivos
   necessários. Segunda chamada busca esses arquivos. Máximo de uma rodada extra.

## 4. Cache

Conteúdo de arquivo por `(repo, ref, path)` cacheado 24 h em memória, limitado a 50 MB. Mesmo erro
recorrente não baixa o repositório de novo.

## 5. Limites

- Arquivo individual maior que 200 KB: envia só as janelas, nunca o arquivo inteiro.
- Binários e arquivos gerados ignorados: `node_modules`, `dist`, `*.min.js`, `*.lock`, imagens.
- Monorepo com vários serviços: o vínculo pode informar um **subdiretório** do repositório para
  restringir a busca. Campo `RepositoryLink.subpath`, a adicionar ao Modelo de Dados.
