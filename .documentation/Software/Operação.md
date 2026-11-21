# Operação

**Versão:** 0.2.0

## Preparar um host para o Lognix

O Lognix não instala nada no host. Ele precisa só de SSH e de acesso ao socket do Docker.

1. **Usuário SSH.** Crie um usuário dedicado e coloque-o no grupo `docker`:
   ```bash
   sudo useradd -m -s /bin/bash lognix
   sudo usermod -aG docker lognix
   ```
2. **Autenticação.** Prefira chave. Gere no seu computador e instale a pública no host:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/lognix -N ''
   ssh-copy-id -i ~/.ssh/lognix.pub lognix@HOST
   ```
   Cole o conteúdo de `~/.ssh/lognix` no cadastro. Senha e chave com passphrase também funcionam.
3. **Encaminhamento no sshd.** Em `/etc/ssh/sshd_config`, `AllowTcpForwarding` e
   `AllowStreamLocalForwarding` não podem estar como `no`. O padrão do OpenSSH é `yes`. Após
   alterar, `sudo systemctl restart sshd`.
4. **Rede.** A máquina do Lognix precisa alcançar o host na porta SSH. O host não precisa alcançar o Lognix.

## O que o Lognix faz no host

Só leitura. Toda requisição à Docker API passa por um proxy dentro do Lognix que permite apenas
`GET` em: `/_ping`, `/version`, `/info`, `/containers/json`, `/containers/{id}/json`,
`/containers/{id}/logs`, `/events`, `/images/{id}/json`. Qualquer outra requisição recebe `403` e
é registrada no log do backend com o logger `lognix.audit.docker_proxy`.

Para quem quiser garantia independente do Lognix: use um usuário SSH sem shell
(`usermod -s /usr/sbin/nologin`) e, se desejar, um proxy de socket no próprio host.

## Validação em seis etapas

| Etapa | Falha típica | O que fazer |
|---|---|---|
| 1. Alcançar o host | porta fechada, firewall, endereço errado | confira endereço e porta; libere a porta SSH para a máquina do Lognix |
| 2. Autenticar via SSH | chave não autorizada, senha errada | `ssh-copy-id`, ou confira a senha |
| 3. Fingerprint | a chave do servidor mudou desde o cadastro | se a mudança for esperada, use "Aceitar novo fingerprint" na tela do host; se não, investigue |
| 4. Encaminhar o socket | sshd com forwarding desligado, Docker parado | ajuste `AllowTcpForwarding` / `AllowStreamLocalForwarding`; `systemctl status docker` |
| 5. Falar com o Docker | usuário sem acesso ao socket | `sudo usermod -aG docker USUARIO` e abra nova sessão |
| 6. Listar containers | raro; Docker com problema | veja `docker ps` no host |

## Túnel

Um túnel SSH por host, verificado a cada 15 s. Se cair, o Lognix reconecta com espera crescente de
2 s até 5 min, indefinidamente. O estado aparece na lista de hosts e na tela do host. Fingerprint
divergente **não** reconecta sozinho: exige aceite na interface.

Ao reiniciar o backend, todos os túneis de hosts não removidos são reabertos.

## Remover um host

"Remover" oculta o host e encerra o túnel, preservando dados. Para apagar de fato,
`DELETE /api/v1/hosts/{id}?purge=true` com `{"confirm_name": "<nome>"}`. Na 0.2.0 isso apaga só o
banco; os logs no Loki entram na 0.3.0.
