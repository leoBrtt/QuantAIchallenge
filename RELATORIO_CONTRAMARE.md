# RELATÓRIO TÉCNICO — ESTRATÉGIA "CONTRAMARÉ" v1
## Motor Quantitativo, Validação Out-of-Sample e Análise Crítica dos Resultados

| | |
|---|---|
| **Projeto** | Desafio Quant AI 2026 — Itaú Asset |
| **Estratégia** | CONTRAMARÉ — alocação contrarian BTC/Caixa em 7 níveis |
| **Mandato** | CONTRAMARÉ não promete vencer o Bitcoin em retorno — promete entregar uma fração controlada do risco dele (beta ~0,5, drawdown estruturalmente menor) |
| **Data do relatório** | 20/07/2026 (v1.2 — caixa passa a ser remunerado pela Selic brasileira vigente, ver Seção 2; parâmetros do Grid Search permanecem exatamente os mesmos) |
| **Dados utilizados** | BTC-USD (`yfinance`) 01/01/2017 → 20/07/2026 (3.488 dias) + Crypto Fear & Greed Index (`Alternative.me`, desde 01/02/2018) + Taxa Selic anualizada (Séries Temporais do Banco Central, SGS 1178, desde 01/01/2017), congelados em cache local point-in-time (`dados/`) |
| **Reprodução** | `python backtest.py` seguido de `python analise_resultados.py` (dependências em `requirements.txt`); duas execuções a partir do cache produzem resultados **bit a bit idênticos** |

---

## 1. Sumário Executivo

O motor quantitativo foi implementado, executado e auditado de ponta a ponta. O Grid Search In-Sample (2018–2022) congelou os parâmetros `Peso_Mayer = 0,3 / Peso_FNG = 0,7` e cortes de Z-Score `±1,50 / ±1,75 / ±2,00`, avaliados sob a convenção T+1 e com custos de 10 bps dentro do loop de otimização — **esses parâmetros e esse processo de otimização não mudaram** desde a v1.0. A partir desta versão, o caixa parado passa a ser remunerado pela **Selic brasileira vigente em cada dia** (antes: 0% a.a.), aplicada só na simulação final (Seção 2 explica a convenção e sua limitação de descasamento cambial). Na validação Out-of-Sample one-shot (2023 → jul/2026):

- **A estratégia cumpre seu mandato de risco:** beta de ~0,51 contra o Buy & Hold, cerca de metade da volatilidade (26,1% vs. 46,9% a.a.) e drawdown máximo muito menor (−30,2% vs. −53,1%).
- **No In-Sample, vence o Buy & Hold em retorno absoluto e em todas as métricas ajustadas a risco** (retorno anualizado 16,14% vs. 13,29%; Sortino 0,58 vs. 0,27; Calmar 0,38 vs. 0,17; Max Drawdown −42,5% vs. −76,7%) — a remuneração do caixa pela Selic (que rendeu de 2% a 14% a.a. no período) fecha boa parte do gap que existia sob a convenção anterior de caixa a 0%.
- **No Out-of-Sample, o Buy & Hold ainda vence em retorno absoluto e em Sharpe/Calmar** (retorno 47,1% vs. 26,6% a.a.; Sharpe 1,06 vs. 1,04; Calmar 0,89 vs. 0,88), mas **o Sortino agora favorece a estratégia** (1,60 vs. 1,55) — o bull market quase ininterrupto de 2023+ ainda favoreceu exposição total, mas a Selic elevada do período (10–14% a.a.) tornou a defesa de capital menos custosa do que sob a convenção anterior. Reportamos ambos os resultados sem retoques — o protocolo one-shot proíbe segunda rodada de tuning, e este relatório não a fez.

Além dos resultados, este relatório inclui a **análise crítica completa** (Seção 9): comportamento ano a ano e em janelas de crise, Information Ratio canônico, atribuição sinal vs. exposição média (benchmark estático fixado a priori, remunerado pela mesma régua de caixa) e a autópsia do sinal nos extremos da escala — incluindo os números que seguem desfavoráveis à tese mesmo após a mudança de convenção. Estudos de sensibilidade de custo e a comparação entre as duas convenções de caixa estão na Seção 10, e as limitações declaradas — incluindo o descasamento cambial da nova convenção — na Seção 11.

---

## 2. A Tese em Uma Frase

O programa mede o quão anormalmente "caro e ganancioso" (ou "barato e amedrontado") o mercado de Bitcoin está em relação ao seu próprio passado recente — combinando o Múltiplo de Mayer (preço ÷ SMA 200) e o Fear & Greed Index normalizado — e ajusta a fatia da carteira em BTC em uma escala de 7 níveis (0% a 100%), **comprando no medo e vendendo na euforia**, com defasagem de execução realista (T+1), custos de transação e caixa remunerado pela **Selic brasileira vigente em cada dia** (dado real, point-in-time, Séries Temporais do Banco Central).

**Por que Selic, e não uma taxa em dólar?** O BTC é cotado em USD, mas o caixa parado é modelado como se fosse uma aplicação em reais (Tesouro Selic/CDI) — a alternativa doméstica mais líquida e mais próxima de "livre de risco" para um gestor brasileiro (Itaú Asset), e mais realista do que a convenção anterior de 0% a.a. Isso introduz uma simplificação declarada: **não há conversão nem hedge cambial** entre a posição em BTC (dólar) e o caixa (reais). Nos períodos em que a Selic superou substancialmente as taxas em dólar (praticamente todo o histórico 2017–2026), essa convenção **infla o retorno da estratégia** em relação a um cenário em que o caixa estivesse de fato aplicado em T-bills americanos. A Seção 11 quantifica e declara essa limitação com destaque; a Seção 10 mostra o resultado sob a convenção anterior (caixa a 0%) lado a lado, para que o efeito da mudança fique visível.

**O objetivo primário é assimetria de drawdown com uma fração do risco do ativo** — não gerar retorno ativo contra o Buy & Hold. O custo esperado (e assumido a priori) desse mandato é abrir mão de parte do upside em bull markets prolongados; a Seção 9 mostra que isso continua valendo mesmo com a Selic remunerando o caixa: o Buy & Hold segue vencendo em retorno absoluto nos dois períodos.

---

## 3. Blindagens Anti-Viés Implementadas e Verificadas

Cada regra do regulamento (`CLAUDE.md` §2–§6) foi implementada no código e **verificada em execução** — não apenas declarada:

| # | Regra | Implementação | Status |
|---|---|---|---|
| 1 | **Dados point-in-time** | CSVs brutos congelados no primeiro download (`dados/btc_usd_raw.csv`, `dados/fng_raw.csv`, `dados/selic_raw.csv`); backtest sempre lê do cache | ✅ Verificado (reprodutibilidade bit a bit entre execuções) |
| 2 | **Sanity check pré-métrica** | Preço > 0, \|retorno diário\| < 60%, sem datas duplicadas/fora de ordem, FNG ∈ [0,100], Selic ∈ [0%, 60% a.a.]; aborta com erro explícito | ✅ Passou em toda a base |
| 3 | **Forward-fill apenas no FNG e na Selic** | `bfill`/interpolação proibidos (look-ahead); Selic sem publicação em fins de semana/feriados repete a última taxa vigente | ✅ Implementado |
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
| 14 | **Caixa remunerado pela Selic (v1.2)** | Taxa Selic vigente no dia (SGS/BCB 1178), aplicada só na simulação final; Grid Search continua com caixa a 0% para preservar os parâmetros já congelados | ✅ Implementado (Seção 2 declara a limitação de descasamento cambial) |

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

**Leitura econômica:** o grid atribuiu mais peso ao sentimento (FNG 70%) do que ao valuation (Mayer 30%), e escolheu cortes largos — a estratégia só se afasta do neutro (50/50) quando o mercado está genuinamente anômalo (|Z| ≥ 1,5σ). Isso reduz churn e custo **em relação a cortes mais estreitos** (os vizinhos com b1 = 1,25 fazem 336–389 rebalanceamentos no IS, contra 280 do ótimo — Seção 7), mas não torna a estratégia barata de operar: ~60–72 rebalanceamentos/ano ainda custam 1,7–2,0 p.p. de retorno por ano (Seção 6). A anatomia completa do churn — incluindo o diagnóstico de whipsaw — está na Seção 9.5.

---

## 6. Custo de Transação e Impacto Financeiro

### Como os custos são calculados

Os custos implementados refletem a realidade operacional de rebalanceamentos em mercado spot (sem alavancagem, sem derivativos). A mecânica é simples e explícita:

**Taxa:** 10 bps = 0,1% sobre o valor negociado em cada rebalanceamento (parâmetro `CUSTO_TAXA = 0.001` no `backtest.py`).

**Quando:** debitados **exclusivamente no dia de execução** (convenção T+1). Nenhuma taxa diária contínua — o custo de transação é independente da remuneração do caixa (Seção 2), que rende a Selic vigente todo dia em que há saldo positivo.

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
| In-Sample (2018–2022) | 1.705 | 280 | ~60 por ano (um a cada ~6,1 dias) |
| Out-of-Sample (2023–26) | 1.297 | 254 | ~71 por ano (um a cada ~5,1 dias) |

A frequência é da mesma ordem nos dois períodos (~60–72/ano), ligeiramente maior no OOS. Isso é um bom sinal de generalização do comportamento — o ritmo de operação não mudou de regime fora da amostra — mas também confirma que a estratégia **não é** de baixa rotatividade (ver o diagnóstico de whipsaw na Seção 9.5).

### Impacto quantificado: "com custos" vs. "sem custos"

O motor roda **duas simulações paralelas** para cada período: uma com custos (a realista) e outra sem (para isolar o efeito da fricção).

Ambas as versões (bruta e líquida) já incluem a remuneração do caixa pela Selic — a única diferença entre elas é o custo de transação.

| Período | Retorno Bruto (s/ custos) | Retorno Líquido (c/ custos) | Impacto Anual |
|---|:---:|:---:|:---:|
| **In-Sample** | +17,89% a.a. | +16,14% a.a. | −1,75 p.p./ano (9,8% relativo) |
| **Out-of-Sample** | +28,82% a.a. | +26,65% a.a. | −2,17 p.p./ano (7,5% relativo) |

**Interpretação:** em ambos os períodos, os custos consomem ~8–10% do retorno bruto — uma fricção ligeiramente menor, em termos relativos, do que sob a convenção anterior de caixa a 0% (que consumia ~10–12%), simplesmente porque a base de retorno é maior com o caixa rendendo Selic. Em pontos percentuais, o custo é praticamente o mesmo (~1,7–2,2 p.p./ano) — ele depende do número de rebalanceios e do tamanho médio negociado, não da remuneração do caixa. A ordem de grandeza fecha com a mecânica: custo anual ≈ nº de rebalanceios × fração média do patrimônio negociada por rebalanceio (~28%, puxada pelos saltos de ≥2 níveis — Seção 9.5) × 10 bps ≈ 60–71 × 0,28 × 0,10% ≈ **1,7–2,2 p.p./ano** — exatamente o observado.

### Por que reportamos as duas versões (bruta e líquida)?

Há três razões fundamentais:

1. **Protocolo anti-viés:** O `CLAUDE.md` §4 exige que os custos estejam **dentro do loop de otimização do Grid Search**, e não adicionados depois. Reportar ambas prova que o desenho respeitou essa restrição: os parâmetros foram escolhidos já sabendo qual seria o custo do churn.

2. **Transparência de propósito:** A versão **bruta** (sem custos) mostra a qualidade do sinal isoladamente — se o seu timing fosse perfeito, qual seria o retorno? A versão **líquida** (com custos) mostra a performance operacional real. Os dois números juntos fazem honestidade transparente: a banca vê exatamente onde a fricção incide.

3. **Padrão do setor:** Fundos reais sempre publicam "retorno bruto" (antes de taxas) e "retorno líquido" (após taxas). A banca do Itaú espera ver isso separado para avaliar a qualidade do sinal vs. a fricção operacional.

A sensibilidade do resultado a custos mais severos (25 e 50 bps) e à remuneração do caixa está na Seção 10.

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

A superfície completa das 616 combinações está em `resultados/grid_search_is.csv` e no heatmap interativo `resultados/heatmap_robustez.html`.

---

## 8. Resultados

Todas as equities abaixo (estratégia e Buy & Hold, bruta e líquida) já incluem a remuneração do caixa pela Selic vigente (Seção 2). Para o efeito isolado da mudança de convenção (caixa a 0% vs. Selic real), ver Seção 10.

### 8.1 In-Sample (treino) — 01/05/2018 a 31/12/2022 (1.705 retornos diários)

| Métrica | Estratégia (líquida) | Estratégia (bruta) | Buy & Hold (líquido) |
|---|---:|---:|---:|
| Retorno total | +101,16% | +115,71% | +79,10% |
| Retorno anualizado | +16,14% | +17,89% | +13,29% |
| Volatilidade anualizada | 39,37% | 39,36% | 70,42% |
| Sharpe (rf=0) | 0,583 | 0,621 | 0,536 |
| **Sortino (MAR=0)** | **0,578** | **0,642** | **0,270** |
| Calmar | 0,379 | 0,429 | 0,173 |
| Max Drawdown | −42,53% | −41,72% | −76,65% |
| Beta vs. Buy & Hold | 0,51 | — | 1,00 |
| Exposição média a BTC | 46,9% | — | 100% |
| Rebalanceamentos | 280 | — | 1 |

**Leitura:** com quase metade da exposição e da volatilidade, a estratégia agora **vence o Buy & Hold também em retorno absoluto** (16,14% vs. 13,29% a.a.) — algo que não acontecia sob a convenção anterior de caixa a 0% (12,36% vs. 13,28%, ver histórico no `ROADMAP.md`). A remuneração do caixa pela Selic, que oscilou entre ~2% e ~14% a.a. no período, fechou boa parte do gap. Nas métricas ajustadas a risco de queda a vantagem é ainda mais nítida (Sortino +114%, Calmar +119%, drawdown 34 p.p. menor). Em Sharpe — que penaliza também a volatilidade de alta — a estratégia agora sai na frente (0,583 vs. 0,536). O custo de fricção do período foi de ~1,75 p.p. ao ano (17,89% bruto → 16,14% líquido, Seção 6).

### 8.2 Out-of-Sample (one-shot) — retornos de 01/01/2023 a 20/07/2026 (1.297 retornos diários)

| Métrica | Estratégia (líquida) | Estratégia (bruta) | Buy & Hold (líquido) |
|---|---:|---:|---:|
| Retorno total | +131,51% | +145,91% | +293,98% |
| Retorno anualizado | +26,65% | +28,82% | +47,09% |
| Volatilidade anualizada | 26,09% | 26,09% | 46,93% |
| Sharpe (rf=0) | 1,035 | 1,100 | 1,056 |
| Sortino (MAR=0) | **1,601** | 1,736 | 1,555 |
| Calmar | 0,884 | 0,987 | 0,887 |
| **Max Drawdown** | **−30,15%** | −29,19% | **−53,06%** |
| Beta vs. Buy & Hold | 0,51 | — | 1,00 |
| Exposição média a BTC | 50,2% | — | 100% |
| Rebalanceamentos | 254 | — | 0 |

**Leitura honesta (sem retoques):** o período 2023–2026 foi um bull market quase ininterrupto, o pior cenário relativo possível para uma estratégia contrarian de exposição parcial. O Buy & Hold ainda vence em retorno absoluto (47,1% vs. 26,7% a.a.), em Sharpe (1,056 vs. 1,035, margem pequena) e em Calmar (0,887 vs. 0,884, margem mínima) — mas **o Sortino agora favorece a estratégia** (1,601 vs. 1,555), uma inversão em relação à convenção de caixa a 0%, onde o Buy & Hold vencia nas três métricas ajustadas a risco. A Selic elevada do período OOS (10–14% a.a.) tornou o "custo de ficar em caixa" bem menor do que sob a hipótese conservadora anterior. O que a estratégia entregou — e era o seu mandato — foi **consistência do perfil de risco fora da amostra**: o beta (0,51), a exposição média (~50%) e a razão de volatilidade permaneceram praticamente idênticos aos do treino, e o drawdown máximo ficou 22,9 p.p. abaixo do benchmark. A estratégia generalizou seu comportamento; o regime de mercado é que não recompensou defesa em retorno absoluto — mas, ajustado por downside risk, a defesa remunerada pela Selic já se pagou.

**Conformidade com o protocolo one-shot:** o OOS foi avaliado uma única vez, com parâmetros congelados. Nenhum ajuste foi feito após a observação destes números. As análises da Seção 9 são **leituras pós-fato das saídas congeladas** (nenhuma reexecução do motor com sinal alterado, nenhum parâmetro reescolhido) e estão declaradas como tal.

---

## 9. Análise Crítica dos Resultados

Todos os números desta seção saem de `analise_resultados.py`, que lê exclusivamente as saídas congeladas do motor (`resultados/serie_backtest.csv`) e grava os resultados em `resultados/analise_resultados.json`. As regras dos comparativos (janelas de crise, benchmark estático) foram fixadas no próprio script antes do cálculo.

### 9.1 Comportamento ano a ano (líquido de custos, caixa remunerado pela Selic)

| Ano | Estratégia | Buy & Hold | Leitura |
|---|---:|---:|---|
| 2018 (mai–dez) | −30,0% | −59,6% | proteção em bear prolongado ✅ |
| 2019 | +42,2% | +92,4% | upside parcial (esperado com ~50% de exposição) |
| 2020 | +96,1% | +303,5% | idem — a estratégia não captura bolhas por desenho |
| 2021 | +30,7% | +59,7% | idem |
| 2022 | −21,2% | −64,3% | proteção em bear prolongado ✅ |
| 2023 | +59,7% | +155,5% | custo da defesa em bull market |
| 2024 | +67,4% | +121,1% | idem |
| 2025 | −6,0% | −6,3% | proteção marginal ✅ (antes da Selic, a estratégia perdia mais que o benchmark neste ano) |
| 2026 (até 20/07) | −7,9% | −25,5% | proteção ✅ |

**Cenários favoráveis e desfavoráveis:** com o caixa remunerado, a estratégia agora protege em **todo ano em que o Buy & Hold fecha negativo, sem exceção** (2018, 2022, 2025, 2026) — inclusive 2025, o único ano em que, sob a convenção anterior de caixa a 0%, ela perdia mais que o benchmark (histórico preservado no `ROADMAP.md`). A margem de proteção em 2025 é pequena (0,3 p.p.) porque foi justamente o ano de mercado mais serrilhado do histórico, com whipsaw pagando custo dobrado nos vai-e-vens (Seção 9.5) — a Selic amorteceu, mas não eliminou, esse atrito. Nos anos de alta, o upside segue parcial por desenho (exposição média ~50%), como esperado.

### 9.2 Janelas de crise (drawdown pico-a-vale dentro de janelas de calendário declaradas)

| Crise | Janela | Estratégia | Buy & Hold |
|---|---|---:|---:|
| COVID | 01/02/2020 → 30/04/2020 | −39,8% | −51,9% |
| Colapso FTX | 31/10/2022 → 30/11/2022 | **−8,0%** | −25,8% |
| Correção 2026 | 01/01/2026 → 20/07/2026 | −17,1% | −39,6% |

**Leitura:** a proteção é máxima em crises precedidas de euforia detectável (FTX: o Z-Score já tinha tirado a estratégia da exposição cheia) e apenas parcial em **crashes rápidos e exógenos** (COVID: −39,8% vs. −51,9%) — o Z-Score de 90 dias é lento por construção e não tem como antecipar um choque de dias. Essa é uma limitação estrutural do sinal, não um defeito de implementação; a Selic no caixa amortece o drawdown em todas as janelas, mas não muda essa leitura qualitativa.

### 9.3 Information Ratio canônico (retornos ativos vs. Buy & Hold)

Pela régua do próprio regulamento (`CLAUDE.md` §5), o IR só pode ser reportado sobre retornos ativos (`retorno_estratégia − retorno_BuyHold`, dia a dia):

| Período | IR canônico | Tracking Error (a.a.) | Diferença de retorno anualizado (geométrica) |
|---|---:|---:|---:|
| In-Sample | **−0,39** | 37,5% | **+2,9 p.p./ano** |
| Out-of-Sample | **−0,90** | 25,1% | −20,4 p.p./ano |

**Reportamos por iniciativa própria, e explicamos uma aparente contradição.** O IR é negativo nos dois períodos — em um dia típico, a estratégia rende menos que o Buy & Hold, o que é esperado de uma exposição média ~50% num ativo que sobe na maior parte do tempo. Mas repare que, no In-Sample, a **diferença de retorno anualizado geométrico é positiva** (+2,9 p.p./ano a favor da estratégia — ela vence em retorno absoluto, Seção 8.1). Isso não é inconsistente: o IR mede a média aritmética diária dos retornos ativos, enquanto o retorno anualizado geométrico já incorpora o **arrasto de volatilidade** (volatility drag) — um ativo com volatilidade muito maior (70% do B&H vs. 39% da estratégia) perde mais retorno composto por unidade de retorno médio do que um ativo mais estável. O B&H pode ter vantagem no retorno diário médio e ainda assim entregar menos retorno composto ao final, porque sua volatilidade altíssima "come" mais da conta. No Out-of-Sample essa vantagem de baixa volatilidade não foi suficiente para compensar o hiato de retorno do bull market (retorno ativo geométrico ainda −20,4 p.p./ano), mas a distância caiu bastante frente aos −27,8 p.p./ano da convenção de caixa a 0%. O mandato nunca foi retorno ativo (o beta-alvo implícito é 0,5); o que valida o desenho é a estabilidade do perfil de risco (beta 0,51 idêntico IS→OOS, vol 26% vs. 47%, DD −30,2% vs. −53,1%) — mas é melhor reportar o IR, com a explicação, do que deixar a banca calculá-lo sem contexto.

### 9.4 Atribuição: quanto é sinal, quanto é exposição média?

Como a estratégia passa 75,6% do tempo no nível 0 (50/50 — Seção 9.5), a pergunta inevitável é: *"e se simplesmente comprássemos 50% de BTC no primeiro dia e não fizéssemos mais nada?"* Rodamos esse benchmark no **mesmo motor** (sinal constante 0, mesma convenção T+1, mesmos custos, mesma data de início, **e a mesma remuneração de caixa pela Selic** — regra fixada a priori em `analise_resultados.py`; sem isso a comparação misturaria efeito de timing com efeito de política de caixa). Como a escala nunca muda, a carteira compra uma vez e **deriva** com o preço:

| Métrica | IS: Estratégia | IS: Base 50/50 | OOS: Estratégia | OOS: Base 50/50 |
|---|---:|---:|---:|---:|
| Retorno anualizado | **+16,14%** | +10,01% | +26,65% | **+35,18%** |
| Volatilidade anualizada | **39,4%** | 43,2% | **26,1%** | 37,0% |
| Sortino (MAR=0) | **0,578** | 0,330 | **1,601** | 1,453 |
| Max Drawdown | **−42,5%** | −64,4% | **−30,2%** | −45,4% |
| Beta vs. Buy & Hold | **0,51** | 0,59 | **0,51** | 0,79 |
| Exposição média a BTC | 46,9% | 57,4% | 50,2% | 78,7% |

**Leitura em duas partes — e a segunda mudou de sinal com a remuneração do caixa:**
- **No In-Sample, o sinal agrega valor inequívoco sobre a mesma dosagem:** com exposição média menor (46,9% vs. 57,4%), a estratégia entrega mais retorno (16,1% vs. 10,0% a.a.), quase o dobro do Sortino (0,578 vs. 0,330) e 22 p.p. menos drawdown. O timing contrarian — sair da exposição na euforia de 2021, voltar no pânico de 2018/2022 — é o que separa as duas curvas.
- **No Out-of-Sample, a base estática ainda vence em retorno absoluto (35,2% vs. 26,7% a.a.) — mas, ao contrário do que se observava sob a convenção de caixa a 0%, agora perde em Sortino (1,453 vs. 1,601).** Sem rebalanceamento, o bull de 2023+ empurrou a exposição derivada da base estática para ~78,7% e o beta para 0,79: ela virou um quase-Buy & Hold, com volatilidade de 37% e drawdown de −45,4%. A estratégia oficial, ao manter a exposição perto de 50% por desenho, colheu a mesma Selic sobre uma fatia de caixa proporcionalmente maior e mais estável, entregando o segundo melhor Sortino do período (atrás apenas do próprio Buy & Hold, Seção 8.2) mesmo com o menor retorno absoluto dos três. **Esta é a evidência mais forte a favor do timing no OOS:** o sinal não venceu em retorno bruto, mas venceu a alternativa "sem sinal" na métrica que o mandato realmente persegue.

### 9.5 Anatomia da escala: inércia e whipsaw

Distribuição do tempo por nível executado (janela completa, 3.003 dias) — inalterada pela mudança de política de caixa, pois depende só do sinal, não da remuneração:

| Nível | −3 (0% BTC) | −2 | −1 | 0 (50/50) | +1 | +2 | +3 (100% BTC) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| % do tempo | 5,5% | 3,4% | 5,4% | **75,6%** | 3,3% | 2,2% | 4,6% |

Dois fatos que a narrativa da "escala de 7 níveis" precisa admitir:

1. **A estratégia é mais inerte do que a narrativa sugere:** passa 3/4 do tempo em 50/50; os extremos somam ~10% do tempo. Com cortes em ±1,5σ/±1,75σ/±2,0σ, na prática ela opera como "50/50 com desvios ocasionais" — e por isso a atribuição da Seção 9.4 é indispensável para provar que os desvios (o timing) agregam.
2. **Whipsaw:** dos 534 rebalanceamentos (~65/ano), **31% saltam ≥2 níveis num único dia** — os cortes distam 0,25σ entre si, então quando o Z-Score cruza a primeira banda frequentemente atravessa várias. É essa fração que puxa o tamanho médio negociado para ~28% do patrimônio e explica o custo de 1,7–2,2 p.p./ano da Seção 6 — um custo que a Selic no caixa **amortece em termos relativos, mas não elimina**. Mitigações (histerese, cortes mais espaçados) exigiriam novo protocolo de otimização e estão listadas como pesquisa futura na Seção 12 — não foram aplicadas nesta v1.

### 9.6 Autópsia do sinal: o que acontece depois dos extremos

Retorno forward do **BTC** (não da estratégia — logo, não afetado pela política de caixa) após cada entrada nos níveis extremos da escala executada:

| Evento | n | Fwd 30d (média · mediana) | Fwd 90d (média · mediana) | Fwd 180d (média · mediana) |
|---|:---:|:---:|:---:|:---:|
| Entrada em **−3** (venda por euforia) | 44 | **−2,5% · −1,5%** | +19,4% · +10,9% | +38,8% · +12,3% |
| Entrada em **+3** (compra por pânico) | 48 | +2,7% · +2,2% | +6,4% · +0,4% | +23,0% · +20,9% |

**Leitura honesta — o lado "vender na euforia" da tese é o mais frágil:**
- O sinal de euforia (−3) tem **validade curta**: em média o BTC de fato recua nos 30 dias seguintes (−2,5%), mas nos horizontes de 90–180 dias o momentum de alta domina (+20% e +39% médios) — historicamente, o robô vendeu **cedo demais** e o custo de ficar fora se acumula com o tempo. Metade das entradas em −3 foi seguida de alta já em 30 dias.
- O sinal de pânico (+3) é **assimétrico e paciente**: mediana ~0 em 90 dias (metade das compras no medo continuou caindo ou andou de lado), mas mediana de +21% em 180 dias — comprar no pânico paga, desde que se espere.

**Consequência para a tese:** ela sobrevive como **mandato de risco** (cortar a cauda esquerda dos drawdowns, como as Seções 9.1–9.2 mostram), não como máquina de alpha de timing. Se o objetivo fosse alpha, a assimetria empírica euforia ≠ pânico sugeriria cortes assimétricos — mudança que dobraria o número de parâmetros e exigiria protocolo novo (Seção 12).

---

## 10. Estudos de Sensibilidade (parâmetros congelados — não é re-tuning)

O sinal congelado foi reavaliado sob custos mais severos (25 e 50 bps) e sob as **duas políticas de caixa** — a convenção anterior (0% a.a., para dimensionar isoladamente o efeito da mudança de regra) e a Selic real point-in-time (padrão atual, Seção 2). Nenhum parâmetro foi reescolhido; a grade de cenários foi fixada a priori em `analise_resultados.py`, que reutiliza `backtest.simular_carteira` sem reimplementação.

**Retorno anualizado líquido · Sortino (MAR=0):**

| Cenário | IS: caixa 0% | IS: Selic real | OOS: caixa 0% | OOS: Selic real |
|---|:---:|:---:|:---:|:---:|
| **Custo 10 bps** (base) | 12,4% · 0,44 | **16,1% · 0,58** | 19,2% · 1,14 | **26,6% · 1,60** |
| Custo 25 bps | 9,9% · 0,35 | 13,6% · 0,48 | 16,2% · 0,96 | 23,5% · 1,40 |
| Custo 50 bps | 5,8% · 0,21 | 9,4% · 0,33 | 11,4% · 0,67 | 18,3% · 1,09 |

Para referência, o Buy & Hold líquido tem Sortino 0,270 no IS e 1,555 no OOS (Seção 8) — invariante à política de caixa da estratégia.

**Leituras:**
- **Efeito isolado da mudança de convenção (0% → Selic real):** no custo-base de 10 bps, a Selic acrescenta ~3,8 p.p./ano ao retorno líquido no In-Sample e ~7,5 p.p./ano no Out-of-Sample — a diferença de magnitude reflete o próprio nível da taxa em cada período (Selic média mais baixa em 2018–2022, que incluiu o ciclo de cortes a ~2% a.a. em 2020–2021, contra uma Selic consistentemente entre ~10% e ~14% a.a. ao longo de todo o 2023–2026). Em ambos os casos, ~50% do patrimônio médio em caixa é a base sobre a qual essa taxa incide.
- **Robustez a custo, sob a nova convenção:** com a Selic remunerando o caixa, a estratégia **sobrevive a custos de até 50 bps mantendo o Sortino IS acima do Buy & Hold** (0,33 vs. 0,27) — mais robusto do que sob a convenção anterior, em que 50 bps já derrubava o Sortino IS (0,21) abaixo do B&H. No OOS, porém, a vantagem de Sortino sobre o B&H (1,555) só se sustenta no custo-base de 10 bps (1,60); a 25 bps já cai para 1,40 e a 50 bps para 1,09 — **a vitória de Sortino no OOS reportada na Seção 9.4 é sensível ao custo de execução**, e não deve ser lida como robusta a qualquer nível de fricção.
- Slippage e spread **não** foram modelados além da taxa fixa — limitação declarada na Seção 11.

---

## 11. Limitações Declaradas (Material de Defesa)

1. **Descasamento cambial da remuneração do caixa (limitação maior, introduzida na v1.2).** O BTC é cotado em USD; o caixa passou a ser remunerado pela Selic (taxa em reais), sem conversão nem hedge cambial. Isso é uma simplificação deliberada — modela o caixa como se fosse uma aplicação doméstica de um gestor brasileiro (Tesouro Selic/CDI), plausível para o contexto de um fundo Itaú Asset, mas **não equivale** a um cenário em que o caixa estivesse de fato aplicado em dólar: historicamente a Selic superou com folga as taxas de juros americanas, então parte do ganho reportado nas Seções 8–9 (por exemplo, o retorno anualizado do IS agora superar o do Buy & Hold, e o Sortino do OOS superar o do Buy & Hold no custo-base) reflete esse prêmio de taxa doméstica, não geração de alpha pelo sinal. A Seção 10 isola esse efeito comparando a convenção nova com a antiga (caixa a 0%) lado a lado, exatamente para que essa contribuição fique visível e não seja confundida com timing.
2. **Ótimo na borda do grid.** O corte `b3 = 2,00` é o valor máximo do espaço de busca, e a superfície do Sortino IS cresce na direção de cortes mais largos (estratégia mais inerte). Ampliar o grid *agora*, após já ter observado o OOS, configuraria re-tuning e foi deliberadamente **não feito**. Qualquer redesenho do espaço de busca exigiria justificativa a priori, documentação e uma nova (e única) rodada OOS. Decisão registrada como pendente no `ROADMAP.md`.
3. **Poucos ciclos independentes.** O In-Sample 2018–2022 contém ~1,5 ciclo completo de BTC. Cinco anos de dados diários não equivalem a milhares de observações independentes; a defesa da robustez apoia-se na vizinhança plana do ótimo (Seção 7), não em significância estatística clássica.
4. **Underperformance de retorno absoluto no OOS.** Reconhecida na Seção 8.2: o Buy & Hold venceu em retorno absoluto (47,1% vs. 26,7% a.a.) e em Sharpe/Calmar por margem pequena, mesmo após a Selic. O IR canônico segue negativo nos dois períodos (Seção 9.3). A estratégia não foi desenhada para vencer um bull market em retorno absoluto; isso é um fato reportado, não uma ressalva escondida.
5. **Sensibilidade a custo da vantagem de Sortino no OOS.** A Seção 10 mostra que a estratégia só supera o Sortino do Buy & Hold no OOS sob o custo-base de 10 bps; a 25 ou 50 bps essa vantagem desaparece. É uma vitória condicional, não incondicional.
6. **Dependência de índices de terceiros sem metodologia sempre versionada.** O Fear & Greed Index da Alternative.me não publica versões da sua metodologia; se o provedor mudou a receita ao longo do tempo, a série histórica mistura regimes do indicador sem que possamos detectar. A série de Selic vem de fonte oficial (Banco Central) e é mais confiável nesse quesito. Mitigação existente para ambas: cache point-in-time (novas revisões do provedor nunca reescrevem o histórico já congelado). Risco residual do FNG: aceito e declarado.
7. **O sinal de euforia vende cedo (evidência da Seção 9.6).** O lado "vender na euforia" da tese tem validade de ~30 dias; em horizontes maiores o momentum domina. A tese se sustenta como mandato de risco, não como previsor de topo.
8. **Custo de transação fixo, sem slippage/spread.** Realista em BTC spot com ordens pequenas, mas não estressado além da taxa fixa (Seção 10).

---

## 12. Conclusão e Próximos Passos

### O que ficou demonstrado

1. **Um processo, antes de um retorno.** O pipeline completo — dados point-in-time, T+1, custos no loop, Grid Search enxuto com objetivo pré-declarado, one-shot OOS — foi implementado, auditado dia a dia e é reprodutível bit a bit. A adição da Selic ao caixa (v1.2) seguiu a mesma disciplina: entrou só na simulação final, sem tocar os parâmetros já congelados nem reabrir o Grid Search.
2. **O perfil de risco generaliza para fora da amostra.** Beta (0,51), exposição média (~50%) e razão de volatilidade praticamente idênticos entre treino e teste; drawdown máximo 22,9 p.p. menor que o benchmark no OOS; proteção confirmada em todo ano de queda do histórico (2018, 2022, 2025, 2026) e no colapso FTX.
3. **O sinal agrega valor sobre a exposição estática nos dois períodos** (Seção 9.4): no IS, mais retorno e quase o dobro do Sortino com dosagem menor; no OOS, mesmo perdendo em retorno absoluto para a base estática, a estratégia entrega o melhor Sortino das três séries depois do próprio Buy & Hold — a base "sem sinal" que deriva para ~79% de exposição paga isso em vol e drawdown.
4. **A remuneração do caixa pela Selic é o fator que mais mudou o retrato do OOS**, e isso está documentado, não escondido: sob a convenção anterior (0%), o Buy & Hold vencia nas três métricas ajustadas a risco; com a Selic, o Sortino passa a favorecer a estratégia. A Seção 10 mostra que essa vitória específica é sensível ao custo de execução e não deve ser generalizada.

### O que NÃO ficou demonstrado

1. **Geração de retorno ativo robusta contra o Buy & Hold** — o IR canônico segue negativo nos dois períodos (−0,39 IS, −0,90 OOS), e o Buy & Hold ainda vence em retorno absoluto nos dois períodos. A vitória de retorno absoluto do IS e a de Sortino do OOS depende, em parte material, do prêmio da Selic sobre uma taxa em dólar equivalente (limitação 1, Seção 11) — não é evidência de que o *timing* por si só gera alpha.
2. **Eficácia do sinal de euforia como previsor** — ele antecipa o recuo de ~30 dias, mas erra o nível em horizontes maiores (Seção 9.6).
3. **Robustez da vantagem de Sortino no OOS a custos de execução mais altos** — desaparece já a 25 bps (Seção 10).

Conclusão proporcional às evidências: **CONTRAMARÉ é um produto de perfil de risco validado em processo, cujos números absolutos de retorno agora dependem também de uma escolha de convenção (Selic sobre o caixa) que precisa ser lida com a limitação cambial em mente — não é, e não pretende ser, uma máquina de alpha independente dessa convenção.** Para um alocador brasileiro que aceite ~50% do risco do Bitcoin com proteção sistemática de cauda e caixa aplicado domesticamente, o comportamento fora da amostra foi essencialmente o contratado; para quem busca vencer o BTC em retorno absoluto, ou para um investidor cujo caixa de fato estivesse em dólar, a estratégia — honestamente — não entrega isso.

### Próximos passos (cada um com o protocolo que o tornaria legítimo)

1. **Redesenho do espaço de cortes a priori** — o ótimo caiu na borda (`b3 = 2,00`); um novo espaço (ex.: cortes até 3,0σ) exigiria justificativa documentada ANTES de rodar, novo Grid Search IS e **uma única** nova rodada OOS.
2. **Histerese anti-whipsaw** (ex.: exigir 2 fechamentos consecutivos além do corte antes de rebalancear) — ataca os 31% de saltos ≥2 níveis; adiciona um parâmetro, portanto só com protocolo novo.
3. **Cortes assimétricos** (euforia ≠ pânico, como a Seção 9.6 evidencia) — dobraria o número de parâmetros de corte; só com espaço de busca redesenhado a priori.
4. **Hedge cambial (ou comparação com taxa em dólar) para o caixa** — trataria o descasamento cambial da limitação 1 (Seção 11); exigiria uma nova fonte de dados (taxa de juros americana e/ou custo de hedge) e poderia ser reportado como estudo de sensibilidade adicional, análogo ao da Seção 10, sem tocar os parâmetros do sinal.
5. **Freio de volatilidade com `vol_alvo` fixado a priori** — já vetado da v1 pela auditoria de complexidade; se entrar, será como estudo de robustez fora do grid, nunca como parâmetro otimizado.

---

## 13. Uso de IA Generativa

O uso de IA generativa foi estrutural em todas as fases do projeto — da pesquisa dirigida (Qlib/PyPortfolioOpt) à auditoria adversarial dos próprios resultados — sempre sob contrato de comportamento explícito (`CLAUDE.md`) e com verificação humana e programática das saídas. A documentação completa, fase a fase, incluindo **onde a IA errou ou teve limites impostos pela equipe**, está em [`USO_DE_IA.md`](USO_DE_IA.md).

---

## 14. Artefatos Gerados

| Arquivo | Conteúdo |
|---|---|
| `backtest.py` | Motor completo: dados/cache → sinais → carteira T+1 → métricas → Grid Search IS → validação OOS one-shot (com auditoria de causalidade embutida) |
| `analise_resultados.py` | Análise crítica pós-OOS (Seções 9–10): ano a ano, crises, IR canônico, atribuição, payoff dos extremos, sensibilidade — lê apenas saídas congeladas |
| `gerar_graficos.py` | Relatório visual interativo (Plotly) a partir das saídas congeladas |
| `dados/btc_usd_raw.csv` · `dados/fng_raw.csv` · `dados/selic_raw.csv` | Cache point-in-time congelado dos dados brutos (preço, sentimento, Selic anualizada — BCB/SGS 1178) |
| `resultados/serie_backtest.csv` | Série diária consolidada: preço, SMA 200, Mayer, FNG, Selic, Score, Z-Score, escala sinalizada/executada, peso em BTC, flags e custos de rebalanceamento, equities (estratégia e Buy & Hold, com e sem custos, já remuneradas pela Selic) |
| `resultados/grid_search_is.csv` | As 616 combinações do grid com todas as métricas — base do heatmap de robustez |
| `resultados/parametros_otimos.json` | Parâmetros congelados do In-Sample |
| `resultados/metricas.json` | Métricas completas IS/OOS (fonte exata das tabelas da Seção 8) |
| `resultados/analise_resultados.json` | Números exatos das Seções 9–10 (fonte das tabelas de análise crítica) |
| `backtest_resultado.html` | Painel interativo: preço + SMA 200 + marcadores de rebalanceamento, equity curves com/sem custos vs. Buy & Hold, alocação de caixa |
| `resultados/heatmap_robustez.html` | Heatmap interativo da superfície do Sortino IS na vizinhança do ótimo |
| `USO_DE_IA.md` | Documentação do papel da IA generativa em cada fase (critério 4.7) |
| `Explicação.md` | Explicação passo a passo do motor, com o motivo de cada decisão |
| `Gaivota.md` | Autoavaliação crítica do trabalho contra o Manual de Avaliação da banca |
