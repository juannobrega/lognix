# ADR 006 — Provider de IA via OpenRouter e Contabilização de Custos

**Status:** Aceito, aprovado para construção em 2026-11-24 · **Data:** 2026-11-21

## Contexto

O Lognix precisa de um modelo de linguagem para gerar insights e diagnósticos. Cada chamada tem custo
em dinheiro e o produto é de código aberto, instalado por terceiros com a própria chave. O usuário
precisa ver quanto gasta e quantas chamadas são feitas.

## Decisão

1. **Único provider suportado na v1: OpenRouter.** Ele expõe uma API única compatível com o formato
   OpenAI e dá acesso a dezenas de modelos de vários fabricantes. Com isso o usuário escolhe o modelo
   sem o Lognix precisar de um integrador por fabricante.
2. **Configuração pela interface, não por `.env`.** Chave de API e modelo escolhido são cadastrados em
   uma tela de configuração e guardados criptografados no banco. Permite trocar sem reiniciar.
3. **Abstração interna de provider desde o início.** O código fala com uma interface `AIProvider`.
   OpenRouter é a primeira implementação. Outros providers entram pelo roadmap sem refatoração.
4. **Contabilização obrigatória.** Toda chamada registra: horário, modelo, tokens de entrada e saída,
   custo estimado, gatilho que a originou, workload relacionado e o insight gerado. O OpenRouter
   devolve o custo na resposta; quando não devolver, calcula-se pela tabela de preços do modelo.
5. **Visualização de consumo.** A interface mostra chamadas e custo acumulado por período, por host e
   por workload.

## Alternativas consideradas

- **Anthropic direto como padrão.** Melhor modelo para a tarefa, mas amarra o usuário a um fabricante.
  Continua acessível via OpenRouter.
- **Vários providers na v1.** Mais código, mais superfície de erro, sem ganho para o lançamento.
- **Ollama local na v1.** Útil para quem não quer pagar, mas adia-se. Roadmap.
- **Chave no `.env`.** Mais simples, mas obriga reiniciar para trocar e não cabe em configuração
  multiusuário.

## Consequências

- Dependência de um serviço externo. Sem internet, sem IA. Logs e inventário continuam funcionando.
- A tabela de preços dos modelos precisa ser mantida ou obtida da API do OpenRouter.
- A entidade "chamada de IA" entra no modelo de dados como registro de auditoria e custo.
- Trocar de modelo é operação do usuário, não do desenvolvedor.
