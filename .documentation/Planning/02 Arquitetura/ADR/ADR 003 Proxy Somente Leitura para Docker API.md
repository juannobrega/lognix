# ADR 003 — Proxy Somente Leitura para Docker API

**Status:** Aceito · **Data:** 2026-11-21

## Contexto

Quem tem acesso ao `docker.sock` tem controle total do Docker daquela máquina. O Docker não oferece
permissão de somente leitura. O Lognix promete nunca alterar nada no host monitorado, e essa promessa
precisa ser imposta, não só documentada. Em um projeto de código aberto, a garantia deve ser auditável.

## Decisão

O backend coloca um **proxy somente leitura** entre o túnel SSH e todos os consumidores da Docker API,
incluindo o Alloy e o próprio backend. O proxy só repassa requisições `GET`. Qualquer `POST`, `PUT`,
`DELETE` ou `PATCH` é rejeitado e registrado. Nenhum componente conecta no socket do túnel diretamente.

Chamadas permitidas na v1:

| Chamada | Uso |
|---|---|
| `GET /version`, `GET /info` | Saúde do túnel |
| `GET /containers/json` | Inventário e estado |
| `GET /containers/{id}/json` | Inspeção: imagem, labels, variáveis |
| `GET /containers/{id}/logs` | Leitura de logs pelo Alloy |
| `GET /events` | Restart, OOM, exit code |
| `GET /images/{id}/json` | Digest e metadados da imagem para vínculo com repositório |

Isso vira requisito não funcional e teste automatizado: o teste tenta alterar um container através do
proxy e deve falhar.

## Alternativas consideradas

- **Só convenção no código.** Insuficiente. Um bug ou dependência poderia emitir um comando.
- **Proxy de socket instalado no host.** Garantia independente do Lognix, mas viola nada no host. Fica
  como recomendação opcional de endurecimento na documentação de operação.
- **Restrição via SSH.** O SSH pode impedir shell e limitar encaminhamento, mas não filtra métodos HTTP.
  Fica como recomendação complementar: usuário dedicado, chave restrita, sem shell.

## Consequências

- Um salto a mais no caminho dos logs. Custo desprezível frente ao SSH.
- A lista de chamadas permitidas é explícita e versionada. Adicionar uma chamada exige atualizar este ADR.
- Permite auditoria: todo pedido à Docker API de qualquer host passa por um ponto único e pode ser logado.
