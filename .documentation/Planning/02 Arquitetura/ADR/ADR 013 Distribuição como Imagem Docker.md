# ADR 013 — Distribuição como Imagem Docker

**Status:** Proposto · **Data:** 2026-11-26

## Contexto

Até aqui o Lognix se instala clonando o repositório e rodando `docker compose up`, que **constrói**
as imagens na máquina de quem instala. Isso custou 88 dos 158 segundos medidos na instalação limpa,
exige toolchain de build no servidor, e faz cada instalação produzir um binário diferente — o que
torna impossível dizer "você está rodando a 0.3.1" com qualquer confiança.

Um produto de código aberto que se espera que rode em servidor dos outros se distribui como imagem
publicada.

## Decisão

1. **A imagem leva o que é acoplado ao código; fica de fora o que o usuário pode querer trocar.**
   A linha não é "aplicação versus infraestrutura", é **quem manda na configuração**.

   | Peça | Onde | Por quê |
   |---|---|---|
   | Backend + frontend | **na imagem** | mesma versão, sempre |
   | Alloy | **na imagem** | a configuração dele é *gerada pelo backend*. Versão de Alloy que não entenda o que o gerador escreve quebra a coleta, e ninguém fora do projeto tem motivo para escolher essa versão |
   | Loki | **na imagem** | a configuração também é nossa: o Loki 3 passou a rotular `service_name` e `detected_level` sozinho, e o pipeline depende de isso estar desligado |
   | Postgres | **fora** | é um banco: quem instala pode já ter um, querer gerenciado, querer o próprio backup e a própria versão |

   O critério: se o Lognix é quem decide a configuração, a peça viaja junto, porque separá-la só
   cria a chance de alguém rodar uma combinação que nós nunca testamos. Se é o usuário quem decide,
   fica fora.

   Postgres dentro da imagem daria o "sobe com um comando" ao custo de perder backup, atualização e
   dimensionamento independentes — e de reiniciar o banco a cada atualização da aplicação.

2. **Fundir frontend e backend numa imagem.** Hoje são duas, com o nginx servindo estáticos e fazendo
   proxy para o backend. Com imagem publicada isso vira duas imagens para versionar em conjunto, o
   que é um jeito conhecido de alguém acabar rodando frontend novo com backend velho. O FastAPI
   serve os estáticos; o nginx sai.

3. **Registro: GHCR** (`ghcr.io/juannobrega/lognix`). O código já está no GitHub, a autenticação é a
   do próprio Actions, não há limite de pull anônimo como no Docker Hub, e a imagem herda a
   visibilidade do repositório. Espelhar no Docker Hub depois é acrescentar um passo, não mudar a
   decisão.

4. **Duas arquiteturas: `linux/amd64` e `linux/arm64`.** Servidor ARM deixou de ser exceção, e quem
   desenvolve em Mac com Apple Silicon roda ARM. Build multi-arch com `buildx` e QEMU.

5. **Tags: `1.2.3`, `1.2`, `1` e `latest`.** Quem quer previsibilidade fixa a exata; quem quer
   correção automática segue a `1.2`; `latest` existe porque todo mundo tenta, e é melhor que
   aponte para a última estável do que para nada. Pré-1.0 **não** recebe `latest` nem a tag de major:
   `0.x` não promete compatibilidade, e deixar alguém seguir `0` seria prometer.

6. **Proveniência e SBOM** gerados pelo `buildx` e anexados. Imagem de projeto aberto que se pede
   para rodar com acesso a um socket do Docker precisa poder ser auditada.

## Alternativas consideradas

- **Continuar só com build local.** Honesto enquanto o projeto era privado. Insustentável quando o
  objetivo é que estranhos rodem: exige git e toolchain no servidor, e não há o que versionar.
- **Imagem única com tudo dentro, inclusive Postgres.** Atraente para demonstração, ruim para
  operação: um `docker stop` no meio de uma escrita, backup que vira `docker cp`, e atualização da
  aplicação arrastando o banco junto.
- **Alloy e Loki como contêineres próprios, com a versão fixada no compose.** Era o desenho
  anterior, e quase funciona: o compose fixa as versões. Mas o compose é um arquivo que quem
  instala edita, e a combinação testada deixa de ser garantida no instante em que alguém troca uma
  linha. Dentro da imagem, a combinação é a que foi testada.
- **Manter duas imagens, frontend e backend.** Espelha o repositório, mas transfere para quem instala
  a responsabilidade de manter as duas na mesma versão.
- **Docker Hub como registro principal.** Mais descoberta, mas limite de pull anônimo e uma conta a
  mais para administrar. Como espelho, faz sentido.

## Consequências

- O `docker-compose.yml` deixa de ter `build:` e passa a ter `image:`. Quem for desenvolver constrói
  localmente, o que precisa continuar simples e documentado.
- O nginx sai, e com ele a configuração de cache e os cabeçalhos de segurança que vivem nele. Tudo
  isso precisa reaparecer no FastAPI, **incluindo o `404` em `/assets/`** que a
  [correção de 2026-11-26](../../07%20Infraestrutura%20e%20Segurança/Ambientes.md) introduziu: sem
  ele, um `index.html` em cache pede um bundle que não existe e recebe HTML com status 200.
- **A imagem passa a ter três processos**, e portanto precisa de supervisão: se o Loki morre e o
  contêiner segue "saudável" porque a API responde, a coleta para em silêncio. A regra é a de
  sempre em contêiner: morreu um, morre o contêiner, e o `restart` do Docker recomeça tudo.
- A imagem engorda com os binários de Alloy e Loki. É o preço de garantir a combinação.
- A instalação limpa perde os 88 segundos de build e passa a ser o tempo de pull.
- Surge a pergunta de como atualizar: ver ADR 015.
