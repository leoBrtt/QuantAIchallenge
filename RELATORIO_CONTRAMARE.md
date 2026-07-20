# RELATÓRIO TÉCNICO — ESTRATÉGIA "CONTRAMARÉ" v1
## Motor Quantitativo, Validação Out-of-Sample e Análise Crítica dos Resultados

| | |
|---|---|
| **Projeto** | Desafio Quant AI 2026 — Itaú Asset |
| **Estratégia** | CONTRAMARÉ — alocação contrarian BTC/Caixa em 7 níveis |
| **Mandato** | CONTRAMARÉ não promete vencer o Bitcoin em retorno — promete entregar uma fração controlada do risco dele (beta ~0,5, drawdown estruturalmente menor) |
| **Data do relatório** | 20/07/2026 (v1.1 — cache de dados estendido até 20/07 e análise crítica pós-OOS incorporada; nenhum parâmetro foi alterado) |
| **Dados utilizados** | BTC-USD (`yfinance`) 01/01/2017 → 20/07/2026 (3.487 dias) + Crypto Fear & Greed Index (`Alternative.me`, desde 01/02/2018), congelados em cache local point-in-time (`dados/`) |
| **Reprodução** | `python backtest.py` seguido de `python analise_resultados.py` (dependências em `requirements.txt`); duas execuções a partir do cache produzem resultados **bit a bit idênticos** |

---

## 1. Sumário Executivo

O motor quantitativo foi implementado, executado e auditado de ponta a ponta. O Grid Search In-Sample (2018–2022) congelou os parâmetros `Peso_Mayer = 0,3 / Peso_FNG = 0,7` e cortes de Z-Score `±1,50 / ±1,75 / ±2,00`, avaliados sob a convenção T+1 e com custos de 10 bps dentro do loop de otimização. Na validação Out-of-Sample one-shot (2023 → jul/2026):

- **A estratégia cumpre seu mandato de risco:** beta de ~0,51 contra o Buy & Hold, quase metade da volatilidade (26,2% vs. 46,9% a.a.) e drawdown máximo muito menor (−33,6% vs. −53,1%).
- **No In-Sample, vence o Buy & Hold em todas as métricas ajustadas a risco de queda** (Sortino 0,44 vs. 0,27; Calmar 0,27 vs. 0,17; Max Drawdown −45% vs. −77%).
- **No Out-of-Sample, o Buy & Hold vence em Sharpe e Sortino** (1,05 vs. 0,80; 1,55 vs. 1,14): o bull market quase ininterrupto de 2023+ favoreceu exposição total. Reportamos esse resultado sem retoques — o protocolo one-shot proíbe segunda rodada de tuning, e este relatório não a fez.

Além dos resultados, este relatório inclui a **análise crítica completa** (Seção 9): comportamento ano a ano e em janelas de crise, Information Ratio canônico, atribuição sinal vs. exposição média (benchmark estático fixado a priori) e a autópsia do sinal nos extremos da escala — incluindo os números **desfavoráveis** à tese. Estudos de sensibilidade de custo e de remuneração do caixa estão na Seção 10, e as limitações declaradas, na Seção 11.

---

## 2. A Tese em Uma Frase

O programa mede o quão anormalmente "caro e ganancioso" (ou "barato e amedrontado") o mercado de Bitcoin está em relação ao seu próprio passado recente — combinando o Múltiplo de Mayer (preço ÷ SMA 200) e o Fear & Greed Index normalizado — e ajusta a fatia da carteira em BTC em uma escala de 7 níveis (0% a 100%), **comprando no medo e vendendo na euforia**, com defasagem de execução realista (T+1), custos de transação e caixa remunerado a 0% (hipótese conservadora).

**O objetivo primário é assimetria de drawdown com uma fração do risco do ativo** — não gerar retorno ativo contra o Buy & Hold. O custo esperado (e assumido a priori) desse mandato é abrir mão de parte do upside em bull markets prolongados; a Seção 9 mostra que foi exatamente isso que o Out-of-Sample cobrou.

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

**Leitura econômica:** o grid atribuiu mais peso ao sentimento (FNG 70%) do que ao valuation (Mayer 30%), e escolheu cortes largos — a estratégia só se afasta do neutro (50/50) quando o mercado está genuinamente anômalo (|Z| ≥ 1,5σ). Isso reduz churn e custo **em relação a cortes mais estreitos** (os vizinhos com b1 = 1,25 fazem 336–389 rebalanceamentos no IS, contra 280 do ótimo — Seção 7), mas não torna a estratégia barata de operar: ~60–72 rebalanceamentos/ano ainda custam 1,7–2,0 p.p. de retorno por ano (Seção 6). A anatomia completa do churn — incluindo o diagnóstico de whipsaw — está na Seção 9.5.

---

## 6. Custo de Transação e Impacto Financeiro

### Como os custos são calculados

Os custos implementados refletem a realidade operacional de rebalanceamentos em mercado spot (sem alavancagem, sem derivativos). A mecânica é simples e explícita:

**Taxa:** 10 bps = 0,1% sobre o valor negociado em cada rebalanceamento (parâmetro `CUSTO_TAXA = 0.001` no `backtest.py`).

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
| In-Sample (2018–2022) | 1.705 | 280 | ~60 por ano (um a cada ~6,1 dias) |
| Out-of-Sample (2023–26) | 1.296 | 254 | ~72 por ano (um a cada ~5,1 dias) |

A frequência é da mesma ordem nos dois períodos (~60–72/ano), ligeiramente maior no OOS. Isso é um bom sinal de generalização do comportamento — o ritmo de operação não mudou de regime fora da amostra — mas também confirma que a estratégia **não é** de baixa rotatividade (ver o diagnóstico de whipsaw na Seção 9.5).

### Impacto quantificado: "com custos" vs. "sem custos"

O motor roda **duas simulações paralelas** para cada período: uma com custos (a realista) e outra sem (para isolar o efeito da fricção).

| Período | Retorno Bruto (s/ custos) | Retorno Líquido (c/ custos) | Impacto Anual |
|---|:---:|:---:|:---:|
| **In-Sample** | +14,05% a.a. | +12,36% a.a. | −1,69 p.p./ano (12,0% relativo) |
| **Out-of-Sample** | +21,18% a.a. | +19,14% a.a. | −2,04 p.p./ano (9,6% relativo) |

**Interpretação:** em ambos os períodos, os custos consomem ~10–12% do retorno bruto. A ordem de grandeza fecha com a mecânica: custo anual ≈ nº de rebalanceios × fração média do patrimônio negociada por rebalanceio (~28%, puxada pelos saltos de ≥2 níveis — Seção 9.5) × 10 bps ≈ 60–72 × 0,28 × 0,10% ≈ **1,7–2,0 p.p./ano** — exatamente o observado.

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

**Leitura:** com metade da exposição e da volatilidade, a estratégia entrega retorno anualizado comparável ao Buy & Hold e o supera com folga em todas as métricas ajustadas a risco de queda (Sortino +64%, Calmar +58%, drawdown 31 p.p. menor). Em Sharpe — que penaliza também a volatilidade de alta — os dois praticamente empatam (0,498 vs. 0,535). O custo de fricção total do período foi de ~1,7 p.p. ao ano (14,05% bruto → 12,36% líquido).

### 8.2 Out-of-Sample (one-shot) — retornos de 01/01/2023 a 20/07/2026 (1.296 retornos diários)

| Métrica | Estratégia (líquida) | Estratégia (bruta) | Buy & Hold (líquido) |
|---|---:|---:|---:|
| Retorno total | +86,22% | +97,79% | +292,01% |
| Retorno anualizado | +19,14% | +21,18% | +46,92% |
| Volatilidade anualizada | 26,15% | 26,15% | 46,95% |
| Sharpe (rf=0) | 0,799 | 0,864 | 1,053 |
| Sortino (MAR=0) | 1,139 | 1,264 | 1,549 |
| Calmar | 0,569 | 0,648 | 0,884 |
| **Max Drawdown** | **−33,61%** | −32,70% | **−53,06%** |
| Beta vs. Buy & Hold | 0,51 | — | 1,00 |
| Exposição média a BTC | 50,3% | — | 100% |
| Rebalanceamentos | 254 | — | 0 |

**Leitura honesta (sem retoques):** o período 2023–2026 foi um bull market quase ininterrupto, o pior cenário relativo possível para uma estratégia contrarian de exposição parcial. O Buy & Hold venceu em retorno absoluto e também em Sharpe/Sortino/Calmar. O que a estratégia entregou — e era o seu mandato — foi **consistência do perfil de risco fora da amostra**: o beta (0,51), a exposição média (~50%) e a razão de volatilidade permaneceram praticamente idênticos aos do treino, e o drawdown máximo ficou 19,5 p.p. abaixo do benchmark. A estratégia generalizou seu comportamento; o regime de mercado é que não recompensou defesa.

**Conformidade com o protocolo one-shot:** o OOS foi avaliado uma única vez, com parâmetros congelados. Nenhum ajuste foi feito após a observação destes números. As análises da Seção 9 são **leituras pós-fato das saídas congeladas** (nenhuma reexecução do motor com sinal alterado, nenhum parâmetro reescolhido) e estão declaradas como tal.

---

## 9. Análise Crítica dos Resultados

Todos os números desta seção saem de `analise_resultados.py`, que lê exclusivamente as saídas congeladas do motor (`resultados/serie_backtest.csv`) e grava os resultados em `resultados/analise_resultados.json`. As regras dos comparativos (janelas de crise, benchmark estático) foram fixadas no próprio script antes do cálculo.

### 9.1 Comportamento ano a ano (líquido de custos)

| Ano | Estratégia | Buy & Hold | Leitura |
|---|---:|---:|---|
| 2018 (mai–dez) | −31,6% | −59,6% | proteção em bear prolongado ✅ |
| 2019 | +37,9% | +92,4% | upside parcial (esperado com ~50% de exposição) |
| 2020 | +93,4% | +303,5% | idem — a estratégia não captura bolhas por desenho |
| 2021 | +28,0% | +59,7% | idem |
| 2022 | −26,2% | −64,3% | proteção em bear prolongado ✅ |
| 2023 | +49,4% | +155,5% | custo da defesa em bull market |
| 2024 | +59,3% | +121,1% | idem |
| 2025 | **−11,2%** | **−6,3%** | ⚠️ único ano em que perde MAIS que o benchmark |
| 2026 (até 20/07) | −11,9% | −25,9% | proteção ✅ |

**Cenários favoráveis e desfavoráveis:** a estratégia protege em **bears prolongados** (2018, 2022, 2026), entrega upside parcial em bulls (por desenho) e tem seu **pior cenário relativo em mercados serrilhados** — 2025, quando o whipsaw comprou quedas que continuaram caindo e pagou custo dobrado nos vai-e-vens. 2025 é o único ano do histórico em que a estratégia perdeu mais que o Buy & Hold, e está reportado com o mesmo destaque dos anos favoráveis.

### 9.2 Janelas de crise (drawdown pico-a-vale dentro de janelas de calendário declaradas)

| Crise | Janela | Estratégia | Buy & Hold |
|---|---|---:|---:|
| COVID | 01/02/2020 → 30/04/2020 | −39,8% | −51,9% |
| Colapso FTX | 31/10/2022 → 30/11/2022 | **−8,3%** | −25,8% |
| Correção 2026 | 01/01/2026 → 20/07/2026 | −20,1% | −39,6% |

**Leitura:** a proteção é máxima em crises precedidas de euforia detectável (FTX: o Z-Score já tinha tirado a estratégia da exposição cheia) e apenas parcial em **crashes rápidos e exógenos** (COVID: −39,8% vs. −51,9%) — o Z-Score de 90 dias é lento por construção e não tem como antecipar um choque de dias. Essa é uma limitação estrutural do sinal, não um defeito de implementação.

### 9.3 Information Ratio canônico (retornos ativos vs. Buy & Hold)

Pela régua do próprio regulamento (`CLAUDE.md` §5), o IR só pode ser reportado sobre retornos ativos (`retorno_estratégia − retorno_BuyHold`, dia a dia):

| Período | IR canônico | Tracking Error (a.a.) | Diferença de retorno anualizado (geométrica) |
|---|---:|---:|---:|
| In-Sample | **−0,48** | 37,5% | −0,9 p.p./ano |
| Out-of-Sample | **−1,14** | 25,0% | −27,8 p.p./ano |

**Este é o número mais duro do projeto, e o reportamos por iniciativa própria.** Em termos de retorno ativo, a estratégia **destrói valor de forma consistente** contra o Buy & Hold — como qualquer estratégia de exposição média ~50% num ativo que subiu quase ininterruptamente. O mandato nunca foi retorno ativo (o beta-alvo implícito é 0,5); o que valida o desenho é a estabilidade do perfil de risco (beta 0,51 idêntico IS→OOS, vol 26% vs. 47%, DD −33,6% vs. −53,1%), não o IR. Mas uma banca que calcule o IR encontrará exatamente estes valores, e é melhor que os encontre já reportados e interpretados aqui.

### 9.4 Atribuição: quanto é sinal, quanto é exposição média?

Como a estratégia passa 75,5% do tempo no nível 0 (50/50 — Seção 9.5), a pergunta inevitável é: *"e se simplesmente comprássemos 50% de BTC no primeiro dia e não fizéssemos mais nada?"* Rodamos esse benchmark no **mesmo motor** (sinal constante 0, mesma convenção T+1, mesmos custos, mesma data de início — regra fixada a priori em `analise_resultados.py`; como a escala nunca muda, a carteira compra uma vez e **deriva** com o preço):

| Métrica | IS: Estratégia | IS: Base 50/50 | OOS: Estratégia | OOS: Base 50/50 |
|---|---:|---:|---:|---:|
| Retorno anualizado | **+12,36%** | +7,39% | +19,14% | **+34,62%** |
| Volatilidade anualizada | **39,4%** | 44,9% | **26,2%** | 40,1% |
| Sortino (MAR=0) | **0,442** | 0,234 | 1,139 | **1,318** |
| Max Drawdown | **−45,1%** | −67,4% | **−33,6%** | −49,4% |
| Beta vs. Buy & Hold | **0,51** | 0,61 | **0,51** | 0,85 |
| Exposição média a BTC | 47,0% | 59,9% | 50,3% | 85,3% |

**Leitura em duas partes, ambas necessárias:**
- **No In-Sample, o sinal agrega valor inequívoco sobre a mesma dosagem:** com exposição média até *menor* (47% vs. 60%), a estratégia entrega quase o dobro do retorno (12,4% vs. 7,4% a.a.), quase o dobro do Sortino (0,44 vs. 0,23) e 22 p.p. menos drawdown. O timing contrarian — sair da exposição na euforia de 2021, voltar no pânico de 2018/2022 — é exatamente o que separa as duas curvas.
- **No Out-of-Sample, a base estática venceu em retorno e Sortino — mas deixando de ser aquilo que o produto promete.** Sem rebalanceamento, o bull de 2023+ empurrou a exposição derivada para ~85% e o beta para 0,85: a "base 50/50" virou um quase-Buy & Hold, com volatilidade de 40% e drawdown de −49%. Ela ganha abrindo mão precisamente do mandato (perfil de risco constante). A comparação confirma a leitura geral do OOS: **num bull ininterrupto, qualquer regra que aumente exposição vence** — e o que o sinal fez foi manter o perfil contratado, ao custo de retorno.

### 9.5 Anatomia da escala: inércia e whipsaw

Distribuição do tempo por nível executado (janela completa, 3.002 dias):

| Nível | −3 (0% BTC) | −2 | −1 | 0 (50/50) | +1 | +2 | +3 (100% BTC) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| % do tempo | 5,5% | 3,4% | 5,4% | **75,5%** | 3,3% | 2,2% | 4,6% |

Dois fatos que a narrativa da "escala de 7 níveis" precisa admitir:

1. **A estratégia é mais inerte do que a narrativa sugere:** passa 3/4 do tempo em 50/50; os extremos somam ~10% do tempo. Com cortes em ±1,5σ/±1,75σ/±2,0σ, na prática ela opera como "50/50 com desvios ocasionais" — e por isso a atribuição da Seção 9.4 é indispensável para provar que os desvios (o timing) agregam.
2. **Whipsaw:** dos 534 rebalanceamentos (~65/ano), **31% saltam ≥2 níveis num único dia** — os cortes distam 0,25σ entre si, então quando o Z-Score cruza a primeira banda frequentemente atravessa várias. É essa fração que puxa o tamanho médio negociado para ~28% do patrimônio e explica o custo de 1,7–2,0 p.p./ano da Seção 6. Mitigações (histerese, cortes mais espaçados) exigiriam novo protocolo de otimização e estão listadas como pesquisa futura na Seção 12 — não foram aplicadas nesta v1.

### 9.6 Autópsia do sinal: o que acontece depois dos extremos

Retorno forward do **BTC** (não da estratégia) após cada entrada nos níveis extremos da escala executada:

| Evento | n | Fwd 30d (média · mediana) | Fwd 90d (média · mediana) | Fwd 180d (média · mediana) |
|---|:---:|:---:|:---:|:---:|
| Entrada em **−3** (venda por euforia) | 44 | **−2,5% · −1,5%** | +20,3% · +11,5% | +38,8% · +12,3% |
| Entrada em **+3** (compra por pânico) | 48 | +2,7% · +2,2% | +6,4% · +0,4% | +23,0% · +20,9% |

**Leitura honesta — o lado "vender na euforia" da tese é o mais frágil:**
- O sinal de euforia (−3) tem **validade curta**: em média o BTC de fato recua nos 30 dias seguintes (−2,5%), mas nos horizontes de 90–180 dias o momentum de alta domina (+20% e +39% médios) — historicamente, o robô vendeu **cedo demais** e o custo de ficar fora se acumula com o tempo. Metade das entradas em −3 foi seguida de alta já em 30 dias.
- O sinal de pânico (+3) é **assimétrico e paciente**: mediana ~0 em 90 dias (metade das compras no medo continuou caindo ou andou de lado), mas mediana de +21% em 180 dias — comprar no pânico paga, desde que se espere.

**Consequência para a tese:** ela sobrevive como **mandato de risco** (cortar a cauda esquerda dos drawdowns, como as Seções 9.1–9.2 mostram), não como máquina de alpha de timing. Se o objetivo fosse alpha, a assimetria empírica euforia ≠ pânico sugeriria cortes assimétricos — mudança que dobraria o número de parâmetros e exigiria protocolo novo (Seção 12).

---

## 10. Estudos de Sensibilidade (parâmetros congelados — não é re-tuning)

O sinal congelado foi reavaliado sob custos mais severos (25 e 50 bps) e com o caixa remunerado (3% e 5% a.a., capitalização diária coerente com N=365, aplicada só a saldo positivo). Nenhum parâmetro foi reescolhido; a grade de cenários foi fixada a priori em `analise_resultados.py`.

**Retorno anualizado líquido · Sortino (MAR=0):**

| Cenário | IS: caixa 0% | IS: caixa 3% | IS: caixa 5% | OOS: caixa 0% | OOS: caixa 3% | OOS: caixa 5% |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Custo 10 bps** (base) | 12,4% · 0,44 | 14,1% · 0,50 | 15,3% · 0,55 | 19,1% · 1,14 | 20,9% · 1,25 | 22,0% · 1,32 |
| Custo 25 bps | 9,9% · 0,35 | 11,6% · 0,41 | 12,7% · 0,45 | 16,1% · 0,96 | 17,8% · 1,06 | 19,0% · 1,13 |
| Custo 50 bps | 5,8% · 0,21 | 7,5% · 0,27 | 8,6% · 0,30 | 11,3% · 0,66 | 12,9% · 0,76 | 14,0% · 0,83 |

**Leituras:**
- **Custo:** a estratégia sobrevive a 25 bps mantendo a vantagem de Sortino sobre o Buy & Hold no IS (0,35 vs. 0,27). A 50 bps, a fricção consome essa vantagem (Sortino IS 0,21 < 0,27 do B&H) — declaramos abertamente: **a viabilidade da estratégia pressupõe custo de execução de até ~25 bps**, o que é realista em BTC spot com ordens pequenas, mas não em qualquer venue.
- **Caixa remunerado:** com ~50% do patrimônio em caixa na média, cada ponto de remuneração adiciona ~0,5–0,6 p.p./ano. Caixa a 3–5% (T-bills de 2023–2025) melhoraria todas as métricas da estratégia **sem alterar nenhuma conclusão qualitativa** — no OOS o Buy & Hold continua vencendo em retorno e Sortino mesmo no melhor cenário (22,0% · 1,32 vs. 46,9% · 1,55). Por isso mantivemos 0% como convenção-base conservadora: ela desfavorece a estratégia, nunca o benchmark.
- Slippage e spread **não** foram modelados além da taxa fixa — limitação declarada na Seção 11.

---

## 11. Limitações Declaradas (Material de Defesa)

1. **Ótimo na borda do grid.** O corte `b3 = 2,00` é o valor máximo do espaço de busca, e a superfície do Sortino IS cresce na direção de cortes mais largos (estratégia mais inerte). Ampliar o grid *agora*, após já ter observado o OOS, configuraria re-tuning e foi deliberadamente **não feito**. Qualquer redesenho do espaço de busca exigiria justificativa a priori, documentação e uma nova (e única) rodada OOS. Decisão registrada como pendente no `ROADMAP.md`.
2. **Poucos ciclos independentes.** O In-Sample 2018–2022 contém ~1,5 ciclo completo de BTC. Cinco anos de dados diários não equivalem a milhares de observações independentes; a defesa da robustez apoia-se na vizinhança plana do ótimo (Seção 7), não em significância estatística clássica.
3. **Underperformance ajustada a risco no OOS.** Reconhecida na Seção 8.2 e quantificada pelo IR canônico na Seção 9.3 (−1,14 no OOS). A estratégia não foi desenhada para vencer um bull market em retorno absoluto, mas o resultado de Sharpe/Sortino inferior no período de teste é um fato reportado, não uma ressalva escondida.
4. **Convenções conservadoras assumidas:** caixa a 0% a.a. e custo fixo de 10 bps em todos os rebalanceamentos, inclusive na entrada do próprio benchmark — sensibilidade a ambos na Seção 10; slippage e spread não modelados.
5. **Dependência de índice de terceiro sem metodologia versionada.** O Fear & Greed Index da Alternative.me não publica versões da sua metodologia; se o provedor mudou a receita ao longo do tempo, a série histórica mistura regimes do indicador sem que possamos detectar. Mitigação existente: cache point-in-time (novas revisões do provedor nunca reescrevem o histórico já congelado). Risco residual: aceito e declarado.
6. **O sinal de euforia vende cedo (evidência da Seção 9.6).** O lado "vender na euforia" da tese tem validade de ~30 dias; em horizontes maiores o momentum domina. A tese se sustenta como mandato de risco, não como previsor de topo.

---

## 12. Conclusão e Próximos Passos

### O que ficou demonstrado

1. **Um processo, antes de um retorno.** O pipeline completo — dados point-in-time, T+1, custos no loop, Grid Search enxuto com objetivo pré-declarado, one-shot OOS — foi implementado, auditado dia a dia e é reprodutível bit a bit. A Seção 8.2 reporta uma derrota em Sharpe/Sortino no OOS sem retoque algum: essa é a evidência mais forte de que o protocolo foi respeitado.
2. **O perfil de risco generaliza para fora da amostra.** Beta (0,51), exposição média (~50%) e razão de volatilidade idênticos entre treino e teste; drawdown máximo 19,5 p.p. menor que o benchmark no OOS; proteção confirmada nos três bears do histórico (2018, 2022, 2026) e no colapso FTX.
3. **O sinal agrega valor sobre a exposição estática no período de treino** (Seção 9.4): mesmo com dosagem média menor, quase dobra retorno e Sortino da base 50/50 com deriva.

### O que NÃO ficou demonstrado

1. **Geração de retorno ativo contra o Buy & Hold** — o IR canônico é negativo nos dois períodos (−0,48 IS, −1,14 OOS). Num bull ininterrupto, exposição parcial custa caro, e o histórico disponível não contém um regime em que a estratégia gere alpha absoluto.
2. **Eficácia do sinal de euforia como previsor** — ele antecipa o recuo de ~30 dias, mas erra o nível em horizontes maiores (Seção 9.6).
3. **Superioridade ajustada a risco no OOS** — o Buy & Hold venceu também em Sortino no período de teste; a defesa da estratégia no OOS é o drawdown e a estabilidade do perfil, não as razões retorno/risco.

Conclusão proporcional às evidências: **CONTRAMARÉ é um produto de perfil de risco validado em processo, não uma máquina de alpha validada em resultado.** Para um alocador que aceite ~50% do risco do Bitcoin com proteção sistemática de cauda, o comportamento fora da amostra foi exatamente o contratado; para quem busca vencer o BTC, a estratégia — honestamente — não serve.

### Próximos passos (cada um com o protocolo que o tornaria legítimo)

1. **Redesenho do espaço de cortes a priori** — o ótimo caiu na borda (`b3 = 2,00`); um novo espaço (ex.: cortes até 3,0σ) exigiria justificativa documentada ANTES de rodar, novo Grid Search IS e **uma única** nova rodada OOS.
2. **Histerese anti-whipsaw** (ex.: exigir 2 fechamentos consecutivos além do corte antes de rebalancear) — ataca os 31% de saltos ≥2 níveis; adiciona um parâmetro, portanto só com protocolo novo.
3. **Cortes assimétricos** (euforia ≠ pânico, como a Seção 9.6 evidencia) — dobraria o número de parâmetros de corte; só com espaço de busca redesenhado a priori.
4. **Caixa remunerado (CDI/T-bill) como convenção da v2**, com fonte de dados point-in-time própria — a Seção 10 já quantifica o efeito esperado (+0,5–0,6 p.p./ano por ponto de taxa).
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
| `dados/btc_usd_raw.csv` · `dados/fng_raw.csv` | Cache point-in-time congelado dos dados brutos |
| `resultados/serie_backtest.csv` | Série diária consolidada: preço, SMA 200, Mayer, FNG, Score, Z-Score, escala sinalizada/executada, peso em BTC, flags e custos de rebalanceamento, equities (estratégia e Buy & Hold, com e sem custos) |
| `resultados/grid_search_is.csv` | As 616 combinações do grid com todas as métricas — base do heatmap de robustez |
| `resultados/parametros_otimos.json` | Parâmetros congelados do In-Sample |
| `resultados/metricas.json` | Métricas completas IS/OOS (fonte exata das tabelas da Seção 8) |
| `resultados/analise_resultados.json` | Números exatos das Seções 9–10 (fonte das tabelas de análise crítica) |
| `backtest_resultado.html` | Painel interativo: preço + SMA 200 + marcadores de rebalanceamento, equity curves com/sem custos vs. Buy & Hold, alocação de caixa |
| `resultados/heatmap_robustez.html` | Heatmap interativo da superfície do Sortino IS na vizinhança do ótimo |
| `USO_DE_IA.md` | Documentação do papel da IA generativa em cada fase (critério 4.7) |
| `Explicação.md` | Explicação passo a passo do motor, com o motivo de cada decisão |
| `Gaivota.md` | Autoavaliação crítica do trabalho contra o Manual de Avaliação da banca |
