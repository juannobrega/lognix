# ADR 019 — Autoatualização com Opt-in

**Status:** Aceito, construído na 1.5.0 · **Data:** 2026-11-27

## Contexto

O [ADR 018](ADR%20018%20Verificação%20de%20Atualização%20Opcional.md) entregou a descoberta: o
Lognix sabe que existe versão nova e mostra o comando. Faltou o que o pedido original queria — o
**botão**. Quem usa não quer ler um comando, quer confirmar e esperar.

O ADR 018 registrou por que o botão ficou de fora, e a razão não mudou: **um contêiner não troca a
própria imagem.** O que mudou é a decisão de pagar o preço, de forma explícita e reversível.

## A decisão central: o privilégio é escolha de quem instala

O botão só existe se **duas** coisas acontecerem, e nenhuma delas é padrão:

1. quem instala monta o socket do Docker no contêiner do Lognix, com `group_add` para o processo
   não-root alcançá-lo;
2. alguém liga `updates.self_update_enabled` na tela.

Montar o socket dá ao contêiner **controle do Docker daquela máquina** — criar qualquer contêiner,
inclusive um privilegiado. Isso é poder equivalente a root no host do Lognix. A garantia de
somente-leitura do produto continua intacta, porque ela é sobre os **hosts monitorados**, que
continuam sendo alcançados pelo proxy que recusa tudo que não é `GET`. São dois caminhos
diferentes, e o código mantém dois clientes separados de propósito: `lognix/docker/client.py`
nunca escreve, e `lognix/updates/docker.py` só fala com o socket local.

## As outras decisões

1. **Quem troca é um contêiner auxiliar, não o Lognix.** Um `stop` no próprio contêiner mata o
   processo que o chamou no meio da operação. O auxiliar sobe a partir da **imagem nova**,
   rodando `python -m lognix.updates.swap` — não há segundo artefato para distribuir, e o
   auxiliar funcionando já prova que a imagem nova pelo menos executa.

2. **A imagem é baixada antes de qualquer coisa ser tocada.** Se o `pull` falhar, nada aconteceu:
   o contêiner antigo segue rodando e o botão devolve o erro.

3. **A versão vem da lista do registro, nunca do pedido.** A rota aceita `1.5.0`, confere contra as
   tags publicadas em `ghcr.io/juannobrega/lognix` e exige que seja maior que a atual. Uma rota
   que aceitasse referência de imagem arbitrária e a executasse com o socket do host seria
   execução remota de código com um nome bonito.

4. **O contêiner novo nasce com a especificação do antigo**, lida do próprio Docker: variáveis,
   volumes, redes, portas, política de reinício e rótulos. `Cmd` e `Entrypoint` são copiados
   **só quando diferem dos da imagem antiga** — copiar sempre congelaria o comando da versão
   velha numa imagem nova que mudou o seu.

5. **Rollback automático.** O antigo é renomeado, não removido, até o novo ficar **saudável** pelo
   `HEALTHCHECK` que a imagem já declara. Novo que não sobe é removido, e o antigo volta ao nome
   e ao ar. Sem isso, um clique poderia deixar a pessoa sem Lognix e sem tela para consertar.

6. **O auxiliar não é descartado.** Fica como contêiner `lognix-updater`, parado, com os registros
   acessíveis por `docker logs`. É o que permite ao Lognix novo contar, na tela, como terminou a
   atualização que derrubou a tela — inclusive quando ela falhou.

## O risco que nenhuma trava remove

Subir versão roda as **migrações de banco** pendentes. Se uma migração falhar no meio, o rollback
devolve o contêiner antigo para um banco que já avançou — e a versão antiga pode não entender o
esquema novo. O Alembic aplica cada revisão em transação, então uma revisão que falha não fica
pela metade, mas as anteriores dela ficam aplicadas.

Não há como consertar isso de dentro do produto. O que existe é dizer a verdade na hora de
confirmar, e exigir o reconhecimento de que há backup. É o que a tela faz.

## Alternativas consideradas

- **`docker compose up -d` disparado pelo auxiliar.** Exigiria o arquivo do compose e o diretório
  do projeto montados no contêiner, com caminhos que só o host conhece. Clonar a especificação
  pelo próprio Docker não depende de nada de fora.
- **Watchtower ou outro atualizador de terceiro.** Resolve, e é um segundo contêiner com o mesmo
  privilégio, que atualiza sem perguntar e sem rollback. Quem preferir continua podendo usar.
- **Atualizar sem rollback.** Menos código, e transforma o pior caso em "sem Lognix, sem tela".
- **Ligado por padrão quando o socket estiver montado.** Montar socket pode ter sido decisão de
  outra pessoa, para outra finalidade. Duas chaves, não uma.
