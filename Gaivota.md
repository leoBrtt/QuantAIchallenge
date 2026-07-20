# AUTOAVALIAÇÃO HONESTA — PROJETO CONTRAMARÉ × MANUAL DE AVALIAÇÃO OFICIAL
### Desafio Quant AI 2026 (Itaú Asset) · v3, atualizada em 20/07/2026 (após a mudança de convenção do caixa para a Selic vigente)

Este documento responde, critério a critério, à pergunta: **"o trabalho, como está hoje, atende ao que a banca procura?"** — usando o Manual de Avaliação Oficial como régua e as saídas congeladas do motor como evidência. A v1 (17/07) encontrou ~25% da nota descoberta; a v2 (20/07, manhã) fechou essas lacunas. Esta v3 audita o efeito de uma mudança de regra pedida depois: o caixa parado passou a ser remunerado pela **Selic brasileira vigente em cada período** (antes: 0% a.a.), aplicada só na simulação final — os 4 parâmetros do Grid Search **não mudaram** (mesmo Sortino IS = 0,4415, mesma exposição média 47,0%, mesmos 280 rebalanceios). Nada aqui foi retocado: os números favoráveis à mudança são reportados junto com a limitação que ela introduz (descasamento cambial), com o mesmo destaque.

---

## Veredito geral (resposta direta)

**O trabalho, como entrega, permanece fechado — e a mudança de convenção do caixa tornou vários números mais favoráveis, sem enfraquecer o rigor do processo.** Os dois critérios de maior rigor (Modelagem 20% + Backtest 15%) seguem no nível que o Manual descreve como desempenho superior. A novidade mais relevante: **no In-Sample, a estratégia agora vence o Buy & Hold também em retorno absoluto** (16,14% vs. 13,29% a.a.), e no Out-of-Sample o **Sortino passa a favorecer a estratégia** (1,601 vs. 1,555) — uma inversão frente à convenção anterior de caixa a 0%, em que o Buy & Hold vencia nas três métricas ajustadas a risco. Isso é bom para a apresentação, mas exige disciplina redobrada: a melhora depende em parte de uma simplificação (Selic em reais remunerando um ativo cotado em dólar, sem hedge cambial) que **precisa ser declarada com o mesmo destaque que os números bons** — e está.

| # | Critério | Peso | Situação | Síntese |
|---|---|---:|:---:|---|
| 4.1 | Apresentação do robô | 5% | 🟢 | CONTRAMARÉ unificado em relatório, HTMLs e documentos + frase de mandato |
| 4.2 | Conceito da estratégia | 20% | 🟢 | Fenômeno, justificativa e forma de teste completos; tese reposicionada como mandato de risco; nova limitação cambial declarada junto com o ganho de retorno |
| 4.3 | Modelagem | 20% | 🟢 | Estruturada, replicável, 4 parâmetros (inalterados); inércia, whipsaw e limitação do FNG seguem declarados |
| 4.4 | Backtest | 15% | 🟢 | 14 blindagens auditadas; sensibilidade custo × política de caixa (0% vs. Selic real) mostra que a vitória de Sortino no OOS é sensível a custo |
| 4.5 | Análise dos resultados | 15% | 🟢 | Ano a ano, crises, IR canônico, atribuição e payoff — todos recalculados; 2025 deixou de ser o único ano de underperformance |
| 4.6 | Conclusão e próximos passos | 10% | 🟢 | Seção 12 atualizada: ganho de retorno é condicionado à convenção cambial; hedge cambial vira próximo passo |
| 4.7 | Uso de IA generativa | 15% | 🟢 | `USO_DE_IA.md`: 7º caso documentado — a IA sinalizou a limitação cambial por iniciativa própria, sem que fosse pedido |

---

## 4.1 Apresentação do Robô (5%) — 🟢 sem mudança

Identidade CONTRAMARÉ e frase de mandato seguem unificadas em todos os artefatos (relatório, `backtest_resultado.html`, `heatmap_robustez.html`, `Explicação.md`, `USO_DE_IA.md`). A mudança de convenção do caixa não afeta este critério. Nenhum risco residual novo.

---

## 4.2 Conceito da Estratégia (20%) — 🟢 fechado, com uma limitação nova a administrar

**O que temos.** Fenômeno, justificativa comportamental e forma de teste seguem completos (`Explicação.md`, relatório Seção 2). A tese como "mandato de risco" ganhou um adendo importante: a Seção 2 do relatório agora explica **por que** o caixa rende Selic e não uma taxa em dólar — decisão explícita de modelar o caixa como aplicação doméstica de um gestor brasileiro (Tesouro Selic/CDI), coerente com o contexto do desafio (Itaú Asset), mas que introduz descasamento cambial frente ao ativo (BTC, cotado em USD).

**O que mudou desde a v2.** Um ganho de retorno passou a existir onde antes só havia mandato de risco: no IS, a estratégia agora bate o Buy & Hold em retorno absoluto (não só em métricas ajustadas a risco). Isso é positivo para a apresentação, mas **se não for acompanhado da ressalva cambial, pode ser lido pela banca como tentativa de inflar o resultado com uma taxa "de fora do escopo"** do ativo (BTC/USD). A defesa está pronta e é direta: a limitação está declarada com destaque na própria Seção 2 e reforçada na Seção 11 do relatório — não foi omitida nem minimizada.

**Risco residual de defesa (novo, introduzido por esta mudança):** a banca pode perguntar "por que Selic e não uma taxa em dólar (Fed Funds, T-bill)?". Defesa preparada: é a alternativa doméstica mais líquida para um gestor brasileiro, mais realista que 0%, e o efeito isolado da escolha está quantificado lado a lado com a convenção anterior (Seção 10 do relatório) — a banca não precisa confiar cegamente, pode ver o antes/depois.

---

## 4.3 Modelagem (20%) — 🟢 sem mudança nos parâmetros, mecânica documentada

**O que temos.** Os 4 parâmetros livres (`Peso_Mayer=0,3`, `b1=1,50`, `b2=1,75`, `b3=2,00`) são **exatamente os mesmos** de antes da mudança — confirmado por hash MD5 idêntico de `parametros_otimos.json` entre as execuções pré e pós-Selic. A remuneração do caixa foi implementada como parâmetro opcional de `simular_carteira` (`selic_aa`), deixado em `None` (0%) nas chamadas do Grid Search — a otimização nunca viu a Selic.

**Por que isso importa para o critério.** Prova que a mudança foi tratada como **decisão de reporte**, não como reotimização disfarçada: o processo que escolheu os parâmetros continua isolado da mudança de convenção. As fragilidades já conhecidas (inércia de 75,6% do tempo em 50/50, whipsaw de 31% dos rebalanceamentos, dependência de metodologia do FNG) seguem declaradas sem alteração — nenhuma delas depende da política de caixa.

**Risco residual de defesa:** nenhum novo além do item 4.2 (limitação cambial, que é conceitual, não de modelagem).

---

## 4.4 Backtest (15%) — 🟢 mais robusto em uma dimensão, mais frágil em outra — ambas declaradas

**O que temos.** As 13 blindagens anteriores seguem auditadas; uma 14ª foi adicionada (Seção 3 do relatório): caixa remunerado pela Selic vigente, point-in-time (SGS/BCB 1178), aplicada só na simulação final, com sanity check próprio (Selic ∈ [0%, 60% a.a.]).

**O que mudou desde a v2.** A tabela de sensibilidade (Seção 10) foi refeita: em vez de taxas hipotéticas de 3%/5%, compara a Selic real com a convenção anterior (0%) em três níveis de custo (10/25/50 bps). Dois achados, um favorável e um desfavorável, ambos publicados:
- **Favorável:** com a Selic, a estratégia sobrevive a custos de até 50 bps mantendo o Sortino IS acima do B&H (0,33 vs. 0,27) — mais robusto que antes (a 50 bps, sob 0%, o Sortino IS caía a 0,21, abaixo do B&H).
- **Desfavorável, e reportado por iniciativa própria:** a vitória de Sortino no OOS (1,601 vs. 1,555 do B&H) só se sustenta no custo-base de 10 bps; a 25 bps já cai para 1,40, a 50 bps para 1,09 — abaixo do B&H nos dois casos. Não é uma vitória incondicional, e o relatório diz isso explicitamente (Seção 10).

**Risco residual de defesa:** slippage/spread não modelados (declarado); ~1,5 ciclo de BTC no IS (declarado desde a v1); a limitação cambial agora consta como item 1 da lista de limitações (Seção 11), não mais como nota de rodapé.

---

## 4.5 Análise dos Resultados (15%) — 🟢 fechado, com uma reversão importante bem explicada

Todos os números da Seção 9 do relatório foram recalculados com a nova política de caixa (mesmas regras de comparação da v2, fixadas a priori em `analise_resultados.py`, que agora reutiliza `backtest.simular_carteira` em vez de reimplementar a lógica de caixa):

- **(a) Ano a ano (Seção 9.1):** a estratégia agora protege em **todo ano de queda do Buy & Hold, sem exceção** (2018, 2022, 2025, 2026) — 2025 deixou de ser "o único ano perdendo do benchmark" (era −11,2% vs. −6,3% na v2; agora −6,0% vs. −6,3%, uma proteção marginal de 0,3 p.p.). É um resultado mais limpo para a apresentação, e o relatório é honesto sobre a margem ser pequena.
- **(b) IR canônico (Seção 9.3):** IS −0,39 (era −0,48), OOS −0,90 (era −1,14) — ainda negativo nos dois períodos, mas menos. Adicionamos uma explicação que a v2 não tinha: a diferença de retorno geométrico anualizado no IS é **positiva** (+2,9 p.p./ano a favor da estratégia) mesmo com IR negativo — não é contradição, é arrasto de volatilidade (o B&H tem quase o dobro da vol e perde mais retorno composto por isso). Essa explicação é o tipo de profundidade técnica que separa análise crítica de relato de números.
- **(c) Atribuição sinal × exposição (Seção 9.4):** o benchmark estático 50/50 agora usa a **mesma** remuneração de caixa da estratégia oficial (correção importante da v2: sem isso, a comparação misturaria efeito de timing com efeito de política de caixa). Resultado: no IS o sinal segue agregando valor inequívoco; no OOS, a base estática ainda vence em retorno absoluto (35,2% vs. 26,7% a.a.), mas **agora perde em Sortino** (1,453 vs. 1,601) — inversão em relação à v2, em que a base estática vencia nas duas métricas. É a evidência mais forte a favor do timing no período de teste.
- **(d) Payoff dos extremos (Seção 9.6):** essencialmente inalterado (é calculado sobre o preço do BTC, não sobre a política de caixa); pequenos ajustes de décimo por causa de um dia adicional no cache de preço.

**Risco residual de defesa:** a inversão do item (c) é favorável, mas condicionada ao custo-base (ver 4.4) — o relatório já declara essa condicionalidade, então não é um risco não coberto.

---

## 4.6 Conclusão e Próximos Passos (10%) — 🟢 fechado, com a limitação cambial incorporada à síntese

A Seção 12 do relatório foi ajustada para não deixar a leitura mais favorável (retorno absoluto vencido no IS, Sortino vencido no OOS) soar como vitória incondicional:

1. **O que ficou demonstrado** ganhou um quarto item: a remuneração do caixa pela Selic é o fator que mais mudou o retrato do OOS, e isso está documentado, não escondido.
2. **O que NÃO ficou demonstrado** foi reescrito para deixar claro que a vitória de retorno absoluto (IS) e de Sortino (OOS) dependem, em parte material, do prêmio da Selic sobre uma taxa em dólar equivalente — não é evidência de que o timing sozinho gera alpha.
3. **Síntese proporcional atualizada:** "CONTRAMARÉ é um produto de perfil de risco validado em processo, cujos números absolutos agora dependem também de uma escolha de convenção que precisa ser lida com a limitação cambial em mente."
4. **Próximos passos** ganhou um item novo: hedge cambial (ou comparação com taxa em dólar) para o caixa, substituindo o antigo item "caixa remunerado como convenção da v2" — que já foi implementado nesta mesma v3.

---

## 4.7 Uso de IA Generativa (15%) — 🟢 fechado, com um sétimo caso de contenção

`USO_DE_IA.md` ganhou uma linha na tabela fase a fase (Fase 6: mudança de regra dirigida pela equipe) e um sétimo caso na lista de "onde a IA errou, foi corrigida ou teve limites impostos": ao implementar a Selic — pedido explícito, não sugestão da IA —, a IA **identificou por conta própria** a limitação de descasamento cambial antes de publicar os números melhores, em vez de simplesmente reportar o resultado mais bonito sem ressalva. É exatamente o tipo de evidência que sustenta "compreensão do papel da IA": a IA executou a mudança pedida e, adicionalmente, entregou a autocrítica que a tornaria defensável.

---

## O que deliberadamente NÃO foi feito, mesmo havendo tempo

Reotimizar parâmetros, ampliar o grid, trocar a função-objetivo, ou reexecutar o OOS com qualquer variação do sinal — nem mesmo ao adicionar a Selic: o Grid Search continua rodando com caixa a 0%, exatamente para que a mudança de convenção não contaminasse a escolha dos parâmetros. Hedge cambial para o caixa também não foi implementado (fica como próximo passo, Seção 12) — declarar a limitação foi tratado como suficiente para esta versão, não como pretexto para adiar a correção indefinidamente.

## Riscos residuais consolidados (o que ainda pode custar pontos, e a defesa pronta)

| Risco | Defesa preparada |
|---|---|
| "Vocês usaram uma taxa em reais para inflar o retorno de um ativo em dólar" | Declarado com destaque (Seção 2 e 11, item 1); efeito isolado quantificado lado a lado com a convenção anterior (Seção 10); hedge cambial listado como próximo passo (Seção 12) |
| "A vitória de Sortino no OOS não é robusta" | Correto e já declarado: desaparece a partir de 25 bps (Seção 10) — não é escondido, é a própria autoavaliação apontando |
| "Por que a Selic não entra no Grid Search?" | Para não misturar decisão de reporte com reotimização; parâmetros idênticos comprovados por hash (Seção 4.3) |
| "O robô fica 75% do tempo parado em 50/50" | Publicado (9.5) + atribuição provando o valor do timing nos dois períodos (9.4) |
| "O ótimo caiu na borda do grid" | Limitação declarada + próximo passo com protocolo (12) |

---

*Fontes dos números deste documento: `resultados/metricas.json`, `resultados/analise_resultados.json`, `resultados/serie_backtest.csv` e `resultados/grid_search_is.csv` (saídas congeladas de `backtest.py` + `analise_resultados.py`, cache até 20/07/2026, caixa remunerado pela Selic — SGS/BCB 1178). Réguas: Manual de Avaliação Oficial (Criterios_Avaliacao_Desafio.pdf) e `CLAUDE.md` §1–§7. Versões anteriores desta autoavaliação (v1 de 17/07, v2 de 20/07 manhã) preservadas no histórico git.*
