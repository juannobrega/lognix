# Lognix numa imagem só: API, frontend, Loki e Alloy. Ver ADR 013.
#   docker build -t lognix .
#
# Loki e Alloy entram porque a configuração dos dois é nossa — a do Alloy é *gerada* pelo backend —
# e uma combinação de versões que nunca testamos não deveria ser possível de montar. Postgres fica
# de fora porque é um banco: quem instala pode já ter um, ou querer gerenciado.

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Os binários saem das imagens oficiais, então o buildx pega a arquitetura certa em cada build.
FROM grafana/loki:3.3.2 AS loki
FROM grafana/alloy:v1.6.1 AS alloy

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# openssh-client: túneis. gosu: largar o privilégio depois de acertar o dono dos volumes.
# bash: o `wait -n` do supervisor, que o sh do Debian não tem.
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client gosu bash \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY backend/ ./
# A versão vem da tag, pelo pyproject da raiz, e é gravada na imagem: uma instalação precisa poder
# dizer qual versão está rodando sem depender do nome da tag da imagem.
COPY pyproject.toml /lognix-root-pyproject.toml
RUN python -c "import re,pathlib; t=pathlib.Path('/lognix-root-pyproject.toml').read_text(); \
v=re.search(r'(?m)^version = \"([^\"]+)\"', t).group(1); pathlib.Path('lognix/VERSION').write_text(v)" \
 && pip install . && rm /lognix-root-pyproject.toml

COPY --from=frontend /build/dist /app/static
COPY --from=loki /usr/bin/loki /usr/local/bin/loki
COPY --from=alloy /bin/alloy /usr/local/bin/alloy
COPY loki/loki-config.yaml /etc/lognix/loki.yaml
COPY entrypoint.sh /usr/local/bin/lognix-entrypoint

RUN useradd --create-home --uid 10001 lognix \
 && mkdir -p /tunnels /alloy-config /config /var/lib/loki /var/lib/alloy \
 && chmod +x /usr/local/bin/lognix-entrypoint \
 && chown -R lognix:lognix /tunnels /alloy-config /config /app /var/lib/loki /var/lib/alloy
# Sem USER: o entrypoint começa como root para acertar o dono dos volumes e larga o privilégio
# com gosu antes de subir qualquer processo. Nada roda como root.

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status==200 else 1)"
CMD ["lognix-entrypoint"]
