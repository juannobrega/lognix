# ADR 002 — Coleta Remota via Túnel SSH

**Status:** Aceito, aprovado para construção em 2026-11-21 · **Data:** 2026-11-21

## Contexto

O Lognix precisa ler logs de containers em hosts remotos sem instalar nada neles. O Grafana Alloy é a
ferramenta de coleta escolhida, mas seus componentes `discovery.docker` e `loki.source.docker` só
conectam a um daemon Docker por socket Unix ou TCP. Não existe suporte a `ssh://` no Alloy
(verificado na documentação oficial em 2026-11-21).

## Decisão

O Alloy roda **ao lado do Lognix**, não no host. Para cada host cadastrado, o backend abre um túnel SSH
com encaminhamento de socket Unix:

```
ssh -N -L /tunnels/<host>.sock:/var/run/docker.sock <user>@<host>
```

O socket espelhado fica em um volume compartilhado entre backend e Alloy. O Alloy recebe um bloco de
config por host apontando para `unix:///tunnels/<host>.sock` e é recarregado via `/-/reload` quando
hosts entram ou saem. O backend usa o mesmo túnel para consultar a Docker API nas coisas que o Alloy
não cobre: inventário com estado, eventos e inspeção.

O backend é dono de um **supervisor de túneis**: abre, verifica com `GET /version`, vigia, reconecta e
encerra túneis.

## Alternativas consideradas

- **Alloy instalado no host como agente.** Mais eficiente em escala e padrão da Grafana, mas viola o
  requisito de nada no host e exige que o host alcance o Lognix pela rede. Fica no roadmap para
  instalações grandes.
- **Docker API em TCP com TLS no host.** Exige reconfigurar o daemon e gerar certificados em cada host.
  Abre superfície de ataque.
- **Backend lê os logs direto com o SDK Python do Docker via `ssh://`.** Funciona, mas descarta o
  pipeline do Alloy e obriga a reimplementar buffer, retry e labels.

## Consequências

- Requisitos no host: aceitar SSH e o usuário ter acesso ao `docker.sock`, tipicamente via grupo `docker`.
- O Lognix precisa alcançar o host por SSH. O host não precisa alcançar o Lognix.
- Logs trafegam inteiros pelo SSH. Adequado para dezenas de hosts. Centenas exigem o modelo com agente.
- Implementado com `asyncssh` (0.2.0). O sshd do host precisa permitir encaminhamento:
  `AllowTcpForwarding` e `AllowStreamLocalForwarding` não podem estar como `no`. A validação
  detecta isso na etapa 4 e orienta o usuário.
- Se o túnel cair, a coleta daquele host para até reconectar. O supervisor precisa registrar e exibir isso.
