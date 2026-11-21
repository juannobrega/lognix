# 06 — Frontend

Define a interface React + Vite + CSS.

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| Mapa de Telas | Todas as telas, navegação entre elas | A criar |
| Telas Detalhadas | Wireframe textual e comportamento de cada tela | A criar |
| Componentes | Biblioteca de componentes próprios | A criar |
| Estado e Dados | Gerenciamento de estado, cache, tempo real | A criar |
| Design System | Tokens, tipografia, cores, tema claro/escuro | A criar |

## Decisões já tomadas

- **Insights e notificações** ficam na tela principal até o usuário marcar como vistos, um a um ou com "limpar todos". Vistos saem da tela, mas continuam acessíveis em histórico.
- **Containers excluídos** têm aba própria dentro do host. São containers que desapareceram do Docker remoto. Não são monitorados, mas seus insights e padrões continuam consultáveis.
- **Container novo** no host aparece como notificação com ação direta "monitorar" ou "ignorar".
- **Cadastro de host** é um fluxo guiado: credenciais, teste de conexão com motivo de falha legível, lista de containers para seleção.
- **Executor** visível na interface: o que está rodando agora, por projeto, com tipo de trigger, fase e tempo decorrido. Inclui análises manuais e automáticas. Alimentado por WebSocket.
- **Ocorrências sem análise**: lista de triggers disparados enquanto a IA estava desativada ou sem chave.
- **Idioma:** português apenas na v1.
