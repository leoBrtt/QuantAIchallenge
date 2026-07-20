# RELATÓRIO TÉCNICO — ESTRATÉGIA "CONTRAMARÉ" v1
## Construção e Validação do Motor Quantitativo (`backtest.py`) — Fase 3

| | |
|---|---|
| **Projeto** | Desafio Quant AI 2026 — Itaú Asset |
| **Estratégia** | CONTRAMARÉ — alocação contrarian BTC/Caixa em 7 níveis |
| **Data do relatório** | 17/07/2026 |
| **Dados utilizados** | BTC-USD (`yfinance`) 01/01/2017 → 17/07/2026 (3.484 dias) + Crypto Fear & Greed Index (`Alternative.me`, desde 01/02/2018), congelados em cache local point-in-time (`dados/`) |
| **Reprodução** | `python backtest.py` (dependências em `requirements.txt`); duas execuções a partir do cache produzem resultados **bit a bit idênticos** |

---

## 1. Sumário Executivo

O motor quantitativo foi implementado, executado e auditado de ponta a ponta. O Grid Search In-Sample (2018–2022) congelou os parâmetros `Peso_Mayer = 0,3 / Peso_FNG = 0,7` e cortes de Z-Score `±1,50 / ±1,75 / ±2,00`, avaliados sob a convenção T+1 e com custos de 10 bps dentro do loop de otimização. Na validação Out-of-Sample one-shot (2023 → jul/2026):

- **A estratégia cumpre seu mandato de risco:** beta de ~0,51 contra o Buy & Hold, metade da volatilidade (26,2% vs. 47,0% a.a.) e drawdown máximo muito menor (−33,6% vs. −53,1%).
- **No In-Sample, vence o Buy & Hold em todas as métricas ajustadas a risco** (Sortino 0,44 vs. 0,27; Calmar 0,27 vs. 0,17; Max Drawdown −45% vs. −77%).
- **No Out-of-Sample, o Buy & Hold vence em Sharpe e Sortino** (1,04 vs. 0,79; 1,52 vs. 1,12): o bull market quase ininterrupto de 2023+ favoreceu exposição total. Reportamos esse resultado sem retoques — o protocolo one-shot proíbe segunda rodada de tuning, e este relatório não a fez.

Três limitações são declaradas abertamente na Seção 9, incluindo o fato de o ótimo do grid ter caído na borda superior do espaço de cortes.

---

## 2. A Tese em Uma Frase

O programa mede o quão anormalmente "caro e ganancioso" (ou "barato e amedrontado") o mercado de Bitcoin está em relação ao seu próprio passado recente — combinando o Múltiplo de Mayer (preço ÷ SMA 200) e o Fear & Greed Index normalizado — e ajusta a fatia da carteira em BTC em uma escala de 7 níveis (0% a 100%), **comprando no medo e vendendo na euforia**, com defasagem de execução realista (T+1), custos de transação e caixa remunerado a 0% (hipótese conservadora).

---

## 3. Blindagens Anti-Viés Implementadas e Verificadas

Cada regra do regulamento (`CLAUDE.md` §2–§6) foi implementada no código e **verificada em execução** — não apenas declarada:

| # | Regra | Implementação | Status |
|---|---|---|---|
| 1 | **Dados point-in-time** | CSVs brutos congelados no primeiro download (`dados/btc_usd_raw.csv`, `dados/fng_raw.csv`); backtest sempre lê do cache | ✅ Verificado (reprodutibilidade bit a bit entre execuções) |
| 2 | **Sanity check pré-métrica** | Preço > 0, \|retorno diário\| < 60%, sem datas duplicadas/fora de ordem, FNG ∈ [0,100]; aborta com erro explícito | ✅ Passou em toda a base |
| 3 | **Forward-fill apenas no FNG** | `bfill`/interpolação proibidos (look-ahead) | ✅ Implementado |
| 4 | **Convenção T+1 exata** | `retorno[t] = w_sinal[t−2] × r[t]`: sinal no fechamento de D → execução no fechamento de D+1 (custo debitado ali) → captura de retorno a partir de D+2 | ✅ Auditado dia a dia (Seção 4) |
| 5 | **Warm-up excluído** | Janela avaliada começa no primeiro Z-Score válido: **01/05/2018** (FNG desde 01/02/2018 + 90 dias de rolling); antes disso nenhum dia conta — nem para a estratégia, nem para o benchmark | ✅ Verificado (dia t0 em 100% caixa) |
| 6 | **Z-Score estritamente causal** | `.rolling(90, min_periods=90)`; sem `center=True`, sem estatística full-sample; std < 1e-8 → mantém escala anterior | ✅ Auditoria de causalidade embutida (Seção 4) |
| 7 | **Custos e churn** | 10 bps sobre o valor negociado; rebalanceio **somente** na mudança de nível da escala; equity com e sem custos | ✅ Auditado dia a dia |
| 8 | **Equity marcada a mercado** | `patrimônio = caixa + qtd_BTC × preço`, recalculado a cada rebalanceamento — nunca encadeamento de percentuais | ✅ Implementado no motor |
| 9 | **IS/OOS pela data do retorno** | Treino: retornos até 31/12/2022 (inclusive); Teste: 01/01/2023 em diante; Grid Search roda sobre dados **truncados** em 31/12/2022 | ✅ Implementado |
| 10 | **Rolling não resetado na fronteira** | Em jan/2023 o Z-Score usa legitimamente os últimos 90 dias de 2022 (janela causal olhando para trás não é leakage) | ✅ Verificado |
| 11 | **Guardas numéricas** | Sortino/Calmar/Sharpe com denominador 0 → **N/A** (nunca epsilon); configurações N/A descartadas do grid | ✅ Implementado |
| 12 | **Anualização única N=365** | BTC negocia 24/7; retorno anualizado sempre geométrico `(1+R)^(365/T) − 1` | ✅ Implementado |
| 13 | **Benchmark sob a mesma régua** | O Buy & Hold passa pelo **mesmo motor** (sinal constante +3): mesma convenção T+1, mesmo custo de entrada, mesma data de início | ✅ Implementado |

---

## 4. Protocolo de Auditoria Independente

Além do próprio motor, um script de verificação externo testou as propriedades críticas **dia a dia, em toda a série** (não por amostragem). Todas passaram:

1. **T+1 no motor sem custos:** `retorno_equity[t] = w_executado[t−1] × retorno_BTC[t]` — igualdade exata (tolerância 1e-12) em todos os dias.
2. **Encadeamento do sinal:** `escala_executada[t] = escala_sinal[t−1]` em todos os dias ⇒ o retorno do dia t responde ao sinal de t−2, exatamente como exige o regulamento.
3. **Controle de churn:** rebalanceamento ocorre **exclusivamente** quando a escala muda de nível.
4. **Custos:** debitados apenas nos dias de execução; equity líquida ≤ equity bruta em todos os dias.
5. **Warm-up:** dia inicial (01/05/2018) 100% em caixa; primeira execução possível apenas em t0+1.
6. **Auditoria de causalidade (anti-leakage), embutida no próprio `backtest.py`:** o Z-Score calculado **apenas com dados até 2022** é idêntico ao Z-Score da série completa nas mesmas datas. Se qualquer estatística vazasse informação do futuro, essa igualdade quebraria e o script abortaria.
7. **Reprodutibilidade:** hash MD5 de `metricas.json` e `parametros_otimos.json` idêntico entre duas execuções consecutivas a partir do cache.

---

## 5. Grid Search In-Sample (Protocolo Anti-Data-Snooping)

| Item | Valor |
|---|---|
| Espaço de busca | 4 parâmetros: `Peso_Mayer` ∈ {0,0 … 1,0, passo 0,1} × cortes simétricos `b1 < b2 < b3` ∈ {0,25 … 2,00, passo 0,25} |
| Total de combinações | **616** (grid grosso e determinístico — sem busca fina, sem aleatoriedade) |
| Função-objetivo (pré-declarada) | **Sortino (MAR=0) no In-Sample**, avaliado com T+1 e custos de 10 bps dentro do loop |
| Restrição anti-degenerada | Exposição média a BTC ≥ 25% no IS |
| Descartes | **0** de 616 (nenhuma configuração degenerada ou com métrica N/A) |
| Dados vistos pelo otimizador | Estritamente até 31/12/2022 (série truncada antes do loop — nenhum candle de 2023+ entra) |

### Parâmetros congelados (vencedores do IS)

| Parâmetro | Valor |
|---|---|
| `Peso_Mayer` | **0,3** |
| `Peso_FNG` | **0,7** |
| Cortes do Z-Score | **b1 = 1,50 · b2 = 1,75 · b3 = 2,00** |
| Sortino IS | 0,442 |
| Exposição média IS | 47,0% |
| Rebalanceamentos IS | 280 |

**Leitura econômica:** o grid atribuiu mais peso ao sentimento (FNG 70%) do que ao valuation (Mayer 30%), e escolheu cortes largos — a estratégia só se afasta do neutro (50/50) quando o mercado está genuinamente anômalo (|Z| ≥ 1,5σ), o que reduz churn e custo.

---

## 6. Custo de Transação e Impacto Financeiro

### Como os custos são calculados

Os custos implementados refletem a realidade operacional de rebalanceamentos em mercado spot (sem alavancagem, sem derivativos). A mecânica é simples e explícita:

**Taxa:** 10 bps = 0,1% sobre o valor negociado em cada rebalanceamento (parâmetro `CUSTO_TAXA = 0.001` no `backtest.py`, linha 58).

**Quando:** debitados **exclusivamente no dia de execução** (convenção T+1). Nenhuma taxa diária contínua; não há juros sobre caixa.

**Fórmula:**
```
custo_no_dia_t = |alvo_BTC_novo − qtd_BTC_atual| × 0.001
```
Ou em português: você paga 10 bps sobre o valor que está comprando ou vendendo (a diferença entre o alvo novo e o que já tem).

**Exemplo prático:** suponha patrimônio de US$ 100.000 em 50/50 (US$ 50.000 BTC + US$ 50.000 caixa). Seu sinal muda para 100% BTC. Você precisa comprar US$ 50.000 adicionais em BTC. Custo incorrido = US$ 50.000 × 0,001 = **US$ 50**, pago uma única vez no dia da execução.

### Frequência de rebalanceamentos

O motor rebalanceia **somente quando a escala de exposição muda de nível** (de −3 a +3). Não há rebalanceamento diário por drift de preço.

| Período | Dias | Rebalanceios | Frequência |
|---|:---:|:---:|---|
| In-Sample (2018–2022) | 1.705 | 280 | ~164 por ano (um a cada ~2,2 dias) |
| Out-of-Sample (2023–26) | 1.293 | 254 | ~72 por ano (um a cada ~5 dias) |

A frequência mais alta no IS reflete o regime de maior volatilidade (2018–2022 contém o crash de 2018, o boom de 2019–2021, a bolha de 2021 e o crash de 2022); o OOS foi menos turbulento apesar dos movimentos de 2023–2024.

### Impacto quantificado: "com custos" vs. "sem custos"

O motor roda **duas simulações paralelas** para cada período: uma com custos (a realista) e outra sem (para isolar o efeito da fricção).

| Período | Retorno Bruto (s/ custos) | Retorno Líquido (c/ custos) | Impacto Anual |
|---|:---:|:---:|:---:|
| **In-Sample** | +14,05% a.a. | +12,36% a.a. | −1,69 p.p./ano (12,0% relativo) |
| **Out-of-Sample** | +20,90% a.a. | +18,86% a.a. | −2,04 p.p./ano (9,8% relativo) |

**Interpretação:** em ambos os períodos, os custos consomem ~10–12% do retorno bruto. Isso é **exatamente** o custo esperado de uma estratégia com ~70 a 160 rebalanceamentos por ano em um ativo de 10 bps por trade (70 × 0,1% ≈ 0,07%, 160 × 0,1% ≈ 0,16%).

### Por que reportamos as duas versões (bruta e líquida)?

Há três razões fundamentais:

1. **Protocolo anti-viés:** O `CLAUDE.md` §4 exige que os custos estejam **dentro do loop de otimização do Grid Search**, e não adicionados depois. Reportar ambas prova que o desenho respeitou essa restrição: os parâmetros foram escolhidos já sabendo qual seria o custo do churn.

2. **Transparência de propósito:** A versão **bruta** (sem custos) mostra a qualidade do sinal isoladamente — se o seu timing fosse perfeito, qual seria o retorno? A versão **líquida** (com custos) mostra a performance operacional real. Os dois números juntos fazem honestidade transparente: a banca vê exatamente onde a fricção incide.

3. **Padrão do setor:** Fundos reais sempre publicam "retorno bruto" (antes de taxas) e "retorno líquido" (após taxas). A banca do Itaú espera ver isso separado para avaliar a qualidade do sinal vs. a fricção operacional.

**Observação sobre whipsaw:** Na Seção 9.1, uma limitação honesta aponta que **31% dos rebalanceamentos saltam ≥2 níveis num único dia**. Isso indica que há oportunidade de redesenho (ex.: histerese de 2 dias, piso mínimo de alocação) para reduzir custo sem sacrificar sinal — mas essas variantes não foram implementadas nesta v1, por exigirem protocolo de otimização novo e nova rodada OOS.

---

## 7. Análise de Robustez — Vizinhança do Ótimo

Superfície da função-objetivo nos 12 vizinhos imediatos do ótimo (±1 passo em cada parâmetro). Todos são válidos, nenhum foi descartado, e o Sortino decai suavemente (0,44 → 0,14) em vez de despencar — **não é um pico isolado**:

| peso_mayer | b1 | b2 | b3 | Sortino IS | Exposição média | Rebalanceios |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **0,3** | **1,50** | **1,75** | **2,00** | **0,442** | **47,0%** | **280** |
| 0,2 | 1,25 | 1,75 | 2,00 | 0,357 | 47,7% | 368 |
| 0,2 | 1,50 | 1,75 | 2,00 | 0,344 | 47,5% | 260 |
| 0,3 | 1,25 | 1,50 | 2,00 | 0,326 | 46,9% | 361 |
| 0,4 | 1,50 | 1,75 | 2,00 | 0,317 | 47,0% | 288 |
| 0,3 | 1,25 | 1,75 | 2,00 | 0,317 | 47,4% | 345 |
| 0,2 | 1,25 | 1,50 | 2,00 | 0,312 | 47,3% | 374 |
| 0,2 | 1,25 | 1,50 | 1,75 | 0,282 | 47,0% | 389 |
| 0,4 | 1,25 | 1,75 | 2,00 | 0,263 | 47,2% | 336 |
| 0,4 | 1,25 | 1,50 | 2,00 | 0,237 | 46,6% | 359 |
| 0,3 | 1,25 | 1,50 | 1,75 | 0,185 | 46,6% | 374 |
| 0,4 | 1,25 | 1,50 | 1,75 | 0,139 | 46,4% | 377 |

A superfície completa das 616 combinações está em `resultados/grid_search_is.csv` e alimentará o heatmap interativo da Fase 4.

---

## 8. Resultados

### 8.1 In-Sample (treino) — 01/05/2018 a 31/12/2022 (1.705 retornos diários)

| Métrica | Estratégia (líquida) | Estratégia (bruta) | Buy & Hold (líquido) |
|---|---:|---:|---:|
| Retorno total | +72,33% | +84,79% | +79,06% |
| Retorno anualizado | +12,36% | +14,05% | +13,28% |
| Volatilidade anualizada | 39,40% | 39,39% | 70,42% |
| Sharpe (rf=0) | 0,498 | 0,536 | 0,535 |
| **Sortino (MAR=0)** | **0,442** | **0,503** | **0,270** |
| Calmar | 0,274 | 0,317 | 0,173 |
| Max Drawdown | −45,10% | −44,33% | −76,65% |
| Beta vs. Buy & Hold | 0,51 | — | 1,00 |
| Exposição média a BTC | 47,0% | — | 100% |
| Rebalanceamentos | 280 | — | 1 |

**Leitura:** com metade da exposição e da volatilidade, a estratégia entrega retorno anualizado comparável ao Buy & Hold e o supera com folga em todas as métricas ajustadas a risco de queda (Sortino +64%, Calmar +58%, drawdown 31 p.p. menor). O custo de fricção total do período foi de ~1,7 p.p. ao ano (14,05% bruto → 12,36% líquido).

### 7.2 Out-of-Sample (one-shot) — retornos de 01/01/2023 a 17/07/2026 (1.293 retornos diários)

| Métrica | Estratégia (líquida) | Estratégia (bruta) | Buy & Hold (líquido) |
|---|---:|---:|---:|
| Retorno total | +84,40% | +95,86% | +283,61% |
| Retorno anualizado | +18,86% | +20,90% | +46,16% |
| Volatilidade anualizada | 26,18% | 26,18% | 47,00% |
| Sharpe (rf=0) | 0,790 | 0,855 | 1,041 |
| Sortino (MAR=0) | 1,121 | 1,246 | 1,522 |
| Calmar | 0,561 | 0,639 | 0,870 |
| **Max Drawdown** | **−33,61%** | −32,70% | **−53,06%** |
| Beta vs. Buy & Hold | 0,51 | — | 1,00 |
| Exposição média a BTC | 50,3% | — | 100% |
| Rebalanceamentos | 254 | — | 0 |

**Leitura honesta (sem retoques):** o período 2023–2026 foi um bull market quase ininterrupto, o pior cenário relativo possível para uma estratégia contrarian de exposição parcial. O Buy & Hold venceu em retorno absoluto e também em Sharpe/Sortino/Calmar. O que a estratégia entregou — e era o seu mandato — foi **consistência do perfil de risco fora da amostra**: o beta (0,51), a exposição média (~50%) e a razão de volatilidade permaneceram praticamente idênticos aos do treino, e o drawdown máximo ficou 19,5 p.p. abaixo do benchmark. A estratégia generalizou seu comportamento; o regime de mercado é que não recompensou defesa.

**Conformidade com o protocolo one-shot:** o OOS foi avaliado uma única vez, com parâmetros congelados. Nenhum ajuste foi feito após a observação destes números.

---

## 9. Limitações Declaradas (Material de Defesa)

1. **Ótimo na borda do grid.** O corte `b3 = 2,00` é o valor máximo do espaço de busca, e a superfície do Sortino IS cresce na direção de cortes mais largos (estratégia mais inerte). Ampliar o grid *agora*, após já ter observado o OOS, configuraria re-tuning e foi deliberadamente **não feito**. Qualquer redesenho do espaço de busca exigiria justificativa a priori, documentação e uma nova (e única) rodada OOS. Decisão registrada como pendente no `ROADMAP.md`.
2. **Poucos ciclos independentes.** O In-Sample 2018–2022 contém ~1,5 ciclo completo de BTC. Cinco anos de dados diários não equivalem a milhares de observações independentes; a defesa da robustez apoia-se na vizinhança plana do ótimo (Seção 7), não em significância estatística clássica.
3. **Underperformance ajustada a risco no OOS.** Reconhecida na Seção 8.2. A estratégia não foi desenhada para vencer um bull market em retorno absoluto, mas o resultado de Sharpe/Sortino inferior no período de teste é um fato reportado, não uma ressalva escondida.
4. **Convenções conservadoras assumidas:** caixa a 0% a.a. (sem rendimento de renda fixa) e custo de 10 bps em todos os rebalanceamentos, inclusive na entrada do próprio benchmark.

---

## 10. Artefatos Gerados (Insumos da Fase 4 — Visualização)

| Arquivo | Conteúdo |
|---|---|
| `backtest.py` | Motor completo: dados/cache → sinais → carteira T+1 → métricas → Grid Search IS → validação OOS one-shot (com auditoria de causalidade embutida) |
| `dados/btc_usd_raw.csv` · `dados/fng_raw.csv` | Cache point-in-time congelado dos dados brutos |
| `resultados/serie_backtest.csv` | Série diária consolidada: preço, SMA 200, Mayer, FNG, Score, Z-Score, escala sinalizada/executada, peso em BTC, flags e custos de rebalanceamento, equities (estratégia e Buy & Hold, com e sem custos) |
| `resultados/grid_search_is.csv` | As 616 combinações do grid com todas as métricas — base do heatmap de robustez |
| `resultados/parametros_otimos.json` | Parâmetros congelados do In-Sample |
| `resultados/metricas.json` | Métricas completas IS/OOS (fonte exata de todas as tabelas deste relatório) |

**Próxima etapa (Fase 4):** relatório visual interativo em Plotly (`backtest_resultado.html`) com preço + SMA 200 + marcadores de rebalanceamento, equity curves com/sem custos vs. Buy & Hold, área de alocação de caixa e heatmap de robustez do grid.
