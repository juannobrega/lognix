# Prompts

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

Catálogo dos prompts da v1. Os textos finais são escritos e iterados na construção, com teste contra
logs reais. Aqui ficam estrutura, regras e versionamento.

## 1. Regras gerais

- Prompts vivem em arquivos versionados no repositório, um por caso de uso, com número de versão.
- `AICall` grava a versão do prompt usada. Permite comparar qualidade entre versões.
- Idioma da saída: **português** apenas, na v1. Decisão de 2026-11-21. Internacionalização no roadmap.
- O prompt de sistema declara o papel, o formato de saída obrigatório, o esquema JSON e as proibições.
- O prompt de usuário contém só o contexto, em blocos delimitados e rotulados, na ordem do Pipeline seção 2.
- Nenhum prompt pede ação. A IA descreve e sugere; o backend decide o que fazer.

## 2. Prompt IA-1, explicar erro

Sistema, estrutura:

1. Papel: engenheiro de operações analisando logs de um container.
2. Objetivo: explicar o que aconteceu, a causa mais provável e o que fazer.
3. Formato: só JSON no esquema fornecido, sem texto fora dele.
4. Regras: citar evidências por índice; não inventar linhas; se a causa não estiver nos dados, dizer
   isso em `probable_cause` e baixar `confidence`; marcar `needs_code` quando a causa provável está no
   código do aplicativo e não em infraestrutura.
5. Escala de severidade com definição de cada nível.

Usuário, blocos: `[PROJETO]`, `[TRIGGER]`, `[LINHAS DE ERRO]` numeradas, `[CONTEXTO ANTERIOR]`
numerado em sequência, `[EVENTOS DOCKER]` numerados, `[PADRÕES]` numerados, `[REDEPLOY]`, `[ESTADO ATUAL]`.
Índices são globais e únicos entre blocos, para `evidence_refs`.

## 3. Prompt IA-2, diagnosticar no código

Fase GitHub. Entrada: o insight de IA-1 mais arquivos selecionados do repositório, cada um com caminho
e numeração de linhas. Saída: esquema `code_diagnosis` com `file`, `start_line`, `end_line`,
`snippet`, `explanation`, `confidence`, `alternative_locations`. Regras: só apontar arquivos
fornecidos; se nenhum arquivo fornecido contém a causa, dizer qual arquivo seria necessário.

Detalhes de seleção de arquivos na área 09.

## 4. Prompt IA-3, redigir issue

Fase GitHub. Entrada: insight e diagnóstico. Saída: esquema com `title` e `body_markdown`. O corpo
segue template fixo da área 09, com seção de evidências preenchida pelo backend, não pela IA.

## 5. Retry de esquema

Mensagem adicional anexada no retry: a resposta anterior, o erro de validação literal, e a instrução
"responda novamente apenas com o JSON corrigido".

## 6. Avaliação

Conjunto de casos de teste com logs reais anonimizados e saída esperada, mantido no repositório.
Toda mudança de prompt roda contra esse conjunto antes de virar versão nova. Métricas: taxa de JSON
válido na primeira tentativa, severidade correta, evidências pertinentes.
