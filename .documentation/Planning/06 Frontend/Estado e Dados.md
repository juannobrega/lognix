# Estado e Dados

**Status:** Rascunho para revisão · **Atualizado:** 2026-11-21

## 1. Camadas

| Camada | Ferramenta | Guarda |
|---|---|---|
| Servidor | TanStack Query | tudo que vem da API: hosts, projetos, insights, configurações |
| Tempo real | hook `useRealtime` sobre uma única conexão WebSocket | logs ao vivo, executor, contadores |
| Sessão | contexto React | access token em memória, usuário atual |
| UI local | `useState` e URL | filtros, abas, período. Filtros vivem na query string para serem compartilháveis |

Sem Redux ou similar. O estado global é pequeno e o servidor é a fonte de verdade.

## 2. Cliente de API

- Gerado a partir do OpenAPI do backend, tipado. Regerado no CI; divergência quebra o build.
- Interceptor único: anexa access token, em `401` tenta refresh uma vez, se falhar redireciona ao login.
- Erros no formato único da API viram `ApiError` com `code`, `message`, `action`.

## 3. Consultas

| Dado | `staleTime` | Revalidação |
|---|---|---|
| Hosts, projetos | 30 s | ao focar, e por evento WebSocket `hosts` |
| Insights novos, notificações | 30 s | por evento WebSocket |
| Logs históricos | infinito, chave inclui período e filtros | manual |
| Padrões, eventos | 60 s | ao focar |
| Configurações | 5 min | após salvar |
| Consumo | 60 s | ao focar |

Eventos WebSocket invalidam consultas em vez de atualizar o cache à mão, exceto logs ao vivo e
executor, que são fluxos e não passam pelo cache.

## 4. WebSocket

- Uma conexão por aba, aberta após login, com reconexão exponencial até 30 s.
- Inscrições por canal, controladas pelos componentes montados: a tela de logs inscreve
  `logs:{id}` ao montar e cancela ao desmontar.
- Ao reconectar, reinscreve tudo e invalida as consultas afetadas.
- Logs ao vivo: buffer em memória com teto de 5 000 linhas; acima disso descarta as mais antigas e
  mostra "linhas antigas removidas, use o histórico".

## 5. Formulários

- Validação no cliente espelhando as regras do backend, mas a mensagem do backend prevalece.
- Cadastro de host: estado da máquina de validação vem do WebSocket, não de polling.
