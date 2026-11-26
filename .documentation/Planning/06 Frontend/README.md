# 06 — Frontend

Define a interface React + Vite + CSS.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| [Mapa de Telas](Mapa%20de%20Telas.md) | Navegação, todas as telas com rota e fase, estados obrigatórios, tempo real | Rascunho para revisão |
| [Telas Detalhadas](Telas%20Detalhadas.md) | Wireframes textuais do Painel, Cadastro de host, Host, Projeto, Logs, Insight, Configurações › IA | Rascunho para revisão |
| [Componentes](Componentes.md) | Base e domínio, regras | **Aprovado** |
| [Estado e Dados](Estado%20e%20Dados.md) | Camadas, cliente gerado do OpenAPI, consultas, WebSocket, formulários | **Aprovado** |
| [Design System](Design%20System.md) | Tokens, tema, layout, tipografia, identidade | **Aprovado** |

## Decisões já tomadas

- **Insights e notificações** ficam na tela principal até o usuário marcar como vistos, um a um ou com "limpar todos". Vistos saem da tela, mas continuam acessíveis em histórico.
- **Containers excluídos** têm aba própria dentro do host. São containers que desapareceram do Docker remoto. Não são monitorados, mas seus insights e padrões continuam consultáveis.
- **Container novo** no host aparece como notificação com ação direta "monitorar" ou "ignorar".
- **Cadastro de host** é um fluxo guiado: credenciais, teste de conexão com motivo de falha legível, lista de containers para seleção.
- **Executor** visível na interface: o que está rodando agora, por projeto, com tipo de trigger, fase e tempo decorrido. Inclui análises manuais e automáticas. Alimentado por WebSocket.
- **Ocorrências sem análise**: lista de triggers disparados enquanto a IA estava desativada ou sem chave.
- **Idioma:** português apenas na v1.
- **Tela inicial após o login é o Painel:** insights novos, notificações, estado dos hosts e executor. Decidido em 2026-11-21.
