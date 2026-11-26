#!/bin/bash
# Lognix: API, Loki e Alloy no mesmo contêiner. Ver ADR 013.
#
# Regra de supervisão: morreu um, morre o contêiner. A alternativa — seguir de pé com a API
# respondendo e o Loki morto — produz uma instalação que parece saudável e parou de coletar,
# que é o pior estado possível. Com o contêiner caindo, o `restart` do Docker recomeça tudo e a
# falha aparece no log em vez de ficar escondida.
#
# Bash, não sh, por causa do `wait -n`: ele volta no primeiro filho que terminar **e o reapeia**.
# A versão anterior deste script sondava com `kill -0` num laço, e não funcionava — filho morto e
# não reapeado vira zumbi, e `kill -0` num zumbi responde que ele está vivo. O Loki morria na
# partida e o contêiner seguia "saudável".
set -euo pipefail

LOKI_DATA=${LOKI_DATA_DIR:-/var/lib/loki}
ALLOY_DATA=${ALLOY_DATA_DIR:-/var/lib/alloy}
ALLOY_CONFIG=${ALLOY_CONFIG_PATH:-/alloy-config/config.alloy}
USUARIO=${LOGNIX_USER:-lognix}

# Começa como root só para acertar o dono dos volumes e já larga o privilégio. Volume nomeado
# criado por uma versão anterior vem com outro dono — a atualização de quem já rodava Loki e
# Alloy em contêineres próprios cai exatamente aqui.
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$LOKI_DATA" "$ALLOY_DATA" "$(dirname "$ALLOY_CONFIG")" /tunnels
  chown -R "$USUARIO:$USUARIO" "$LOKI_DATA" "$ALLOY_DATA" "$(dirname "$ALLOY_CONFIG")" /tunnels
  exec gosu "$USUARIO" "$0" "$@"
fi

# O Alloy não sobe sem arquivo, e na primeira subida o backend ainda não gerou nenhum: ele só
# escreve quando houver host com container marcado. Arquivo vazio é config válida.
[ -f "$ALLOY_CONFIG" ] || : > "$ALLOY_CONFIG"

encerra() {
  trap - TERM INT
  kill 0 2>/dev/null || true
}
trap encerra TERM INT

echo "lognix: iniciando loki"
# expand-env porque a retenção vem do ambiente: um número aqui seria um número que ninguém muda.
loki -config.file=/etc/lognix/loki.yaml -config.expand-env=true -target=all &

echo "lognix: iniciando alloy"
alloy run "$ALLOY_CONFIG" \
  --server.http.listen-addr=127.0.0.1:12345 \
  --storage.path="$ALLOY_DATA" \
  --disable-reporting &

echo "lognix: migrando o banco"
alembic upgrade head

echo "lognix: iniciando a api"
uvicorn lognix.main:app --host 0.0.0.0 --port 8000 &

# `|| codigo=$?` porque o errexit aborta o script no próprio `wait -n` quando o filho sai com
# erro — e aí a mensagem abaixo, que é a única pista de qual processo caiu, nunca é impressa.
codigo=0
wait -n || codigo=$?
echo "lognix: um dos processos terminou (código $codigo); derrubando o contêiner" >&2
encerra
exit 1
