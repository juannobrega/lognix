# ADR 016 — Deduplicação de Insights

**Status:** Proposto · **Data:** 2026-11-26

## Contexto

Hoje cada trigger que dispara vira uma chamada de IA e um insight novo. Para um container que
falha uma vez, isso é exatamente certo. Para um container em erro contínuo — o caso mais comum de
todos, porque é justamente quando alguém liga o Lognix — é um insight a cada 30 segundos dizendo a
mesma coisa.

Duas consequências, e a segunda é pior que a primeira:

1. **Custo.** Medido com o preço do Haiku 5.5: 2.880 insights por dia, US$ 64 por mês, de **um**
   container. Com um modelo dez vezes mais caro, US$ 637.
2. **A tela de insights deixa de servir.** Mil cópias do mesmo diagnóstico enterram os outros
   problemas. O produto existe para dizer o que está acontecendo; repetir a mesma frase mil vezes
   é dizer menos, não mais.

O segundo motivo basta sozinho. Mesmo que a IA fosse de graça, o comportamento estaria errado.

## Decisão

1. **A chave de deduplicação é `(container, assinatura do erro)`.** A assinatura vem do padrão do
   Drain que domina a janela — o mesmo agrupamento que já alimenta a aba Padrões. Não é o texto da
   linha: "falhou para o usuário 12" e "falhou para o usuário 99" são o mesmo problema.

2. **Insight repetido não cria outro: atualiza o que existe.** Ganha `occurrences`, `last_seen_at`
   e a janela mais recente. Quem olha a tela vê "visto 340 vezes, a última há 2 minutos", que é
   mais informação do que 340 cartões idênticos, e ocupa uma linha.

3. **Sem chamar a IA de novo.** A deduplicação acontece **antes** da chamada: se já existe insight
   ativo para aquela chave, o trigger é registrado, o contador sobe, e nenhum token é gasto. É
   onde está a economia inteira — contexto menor economiza porcentagem, não fazer a chamada
   economiza a chamada.

4. **Uma janela de silêncio, não deduplicação eterna.** Padrão: **6 horas**. Passado esse tempo
   sem nova ocorrência, o problema é tratado como novo e vale uma análise nova — o contexto mudou,
   pode ter sido corrigido e voltado, e a causa pode ser outra. Configurável.

5. **Marcar como visto reabre a contagem.** Se a pessoa viu e tratou, uma ocorrência nova depois
   disso é informação nova, e merece insight novo. Dedupe serve contra ruído, não contra notícia.

6. **Redeploy quebra a deduplicação.** A imagem mudou: o mesmo erro depois de um deploy novo é
   outro erro, e é exatamente o momento em que o diagnóstico importa mais.

## Alternativas consideradas

- **Deduplicar por título gerado pela IA.** Agruparia bem quando o texto sai igual, mas o texto é
  gerado — a mesma falha pode render títulos diferentes, e dois problemas distintos podem render o
  mesmo. Além disso só funcionaria **depois** da chamada, que é o gasto que se quer evitar.
- **Limite rígido de chamadas por hora, por container.** Simples e cego: tanto cala o container
  barulhento quanto engole o segundo problema, diferente, que apareceu logo depois.
- **Deduplicação eterna, até alguém marcar como visto.** Barato demais: um erro que volta três
  dias depois vira uma linha de contador em vez de um aviso.
- **Deixar como está e confiar no botão de ignorar padrão.** É o contorno de hoje. Exige que a
  pessoa descubra o problema, encontre a aba e aja — depois de já ter pago pelas mil chamadas.

## Consequências

- `Insight` ganha `dedupe_key`, `occurrences`, `last_seen_at` e índice por
  `(container_id, dedupe_key, status)`. Migração nova.
- A tela de insights passa a mostrar contagem e primeira/última ocorrência.
- O ciclo passa a gravar `TriggerFired` sem insight com mais frequência, o que é correto: a
  ocorrência existiu, e não virou análise nova de propósito.
- A tela de Consumo deve mostrar quantas chamadas foram **evitadas**. Economia invisível não é
  percebida, e esse número é o argumento do recurso.
