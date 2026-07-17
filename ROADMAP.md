# ROADMAP DE DESENVOLVIMENTO - ROBÔ QUANT AI

Este documento é o nosso checklist vivo. Aqui anotamos o que já foi definido e planejamos as próximas melhorias com base em referências externas antes de escrever o código.

---

## FASE 1: Definição da Tese e Arquitetura [CONCLUÍDO]
- [x] Escolha dos Indicadores: Múltiplo de Mayer + Crypto Fear & Greed Index.
- [x] Modelo de Alocação: Rebalanceamento de Caixa no mercado Spot em 7 níveis (+3 a -3).
- [x] Mecanismo Antivieses 1: Uso de Z-Score móvel (90 dias) para acionar as escalas sem overfitting.
- [x] Mecanismo Antivieses 2: Divisão de dados em In-Sample (Até 2022) e Out-of-Sample (2023+).
- [x] Mecanismo de Otimização: Grid Search algorítmico em Python rodando apenas no In-Sample.

---

## FASE 2: Pesquisa e Benchmarks Externos [CONCLUÍDA]
*Objetivo: Analisar repositórios de referência (ex: Microsoft Qlib e PyPortfolioOpt) para extrair boas práticas sem violar a neutralidade de complexidade.*

### 🔍 Ideias e Boas Práticas Extraídas do Microsoft Qlib:
*(Análise concluída em 16/07/2026 — fontes em `/referencias/qlib/`, referências no formato arquivo:linha)*

**1. Blindagem do cálculo de retornos contra Data Leakage (aplicar na Fase 3, `backtest.py`):**
- [x] **Regra do T+1 (defasagem Sinal → Execução):** o label padrão do Qlib é `Ref($close,-2)/Ref($close,-1)-1` (`qlib/contrib/data/handler.py:90`), e a função `long_short_backtest` tem um parâmetro `shift=1` dedicado a isso (`qlib/contrib/evaluate.py:279-295`, docstring: "trading day will be T+1"). Ou seja, o Qlib nunca deixa a estratégia operar no mesmo candle em que o sinal foi calculado. **Aplicação:** o Score Combinado/Z-Score de 90 dias deve ser calculado com dados até o fechamento do dia D, mas o rebalanceamento (`w_BTC`) só pode ser precificado no fechamento (ou abertura) de D+1 — nunca usar `close[D]` simultaneamente para gerar o sinal e para precificar a operação daquele mesmo dia.
- [x] **Janelas móveis não podem cruzar a fronteira In-Sample/Out-of-Sample:** `trunc_segments()` e o parâmetro `trunc_days` de `RollingGen` (`qlib/workflow/task/gen.py:124-172`) truncam de propósito o fim do período de treino para que uma janela móvel não "enxergue" dados do período de teste. **Aplicação:** nenhuma estatística (média/desvio-padrão) usada no Grid Search In-Sample (até 2022) pode ser calculada sobre o dataset completo (2018–2025) — o Z-Score de 90 dias deve ser sempre `.rolling(90, min_periods=90)` causal (nunca `center=True`, nunca `.mean()`/`.std()` do array inteiro). **Esclarecimento (Auditoria da Fase 2.5):** a recíproca não vale — no início do Out-of-Sample (jan/2023), o Z-Score móvel usar os últimos 90 dias de 2022 é causal e legítimo (dados do passado disponíveis no momento da decisão); **não resetar** o rolling na fronteira, sob pena de jogar fora 3 meses de OOS sem ganho anti-viés algum.
- [x] **Retorno = variação do valor da carteira marcada a mercado, não diferença bruta de preço:** `return_rate = (now_earning + now_cost) / last_account_value` (`qlib/backtest/account.py:283`) — o custo de transação é contabilizado à parte do retorno bruto, permitindo reportar retorno com e sem custo (padrão usado em `risk_analysis_graph`: `return - cost`). **Aplicação:** montar a equity curve a partir de `caixa + posição_BTC * preço` recalculado a cada rebalanceamento, nunca encadeando `%` de variação de preço isoladamente (evita erros de composição quando a alocação muda no meio do caminho).
- [x] **Cuidado com dados "point-in-time" (revisáveis):** `docs/advanced/PIT.rst` alerta que reutilizar a "última versão" de um dado histórico já revisado causa leakage silencioso. **Aplicação:** cachear localmente o CSV bruto assim que baixado (`yfinance` + `Alternative.me`), para o backtest ser 100% reprodutível e não absorver ajustes retroativos futuros nos mesmos preços históricos.

**2. Top 3 métricas de risco do Qlib para adicionar ao relatório (função `risk_analysis`, `qlib/contrib/evaluate.py:26-93`):**
- [ ] **Sharpe (rf=0)** — `mean(retorno)/std(retorno) * sqrt(N)`. **Correção de nomenclatura (Auditoria da Fase 2.5):** o Qlib chama isso de "Information Ratio", mas o IR canônico usa retornos *ativos* vs. benchmark — no nosso relatório a métrica será nomeada **Sharpe (rf=0)**; se quisermos o IR verdadeiro, calculá-lo sobre `retorno_estratégia − retorno_BuyHold` (combina com o Beta bônus abaixo).
- [ ] **Max Drawdown** — `((1+r).cumprod()/(1+r).cumprod().cummax() - 1).min()`; maior perda percentual do pico ao vale da equity curve — essencial dado o risco de cauda do BTC.
- [ ] **Volatilidade (desvio-padrão dos retornos diários)** — `r.std(ddof=1)`; usada isoladamente e como denominador do Information Ratio.
- [ ] *(bônus, não-obrigatório)* **Beta vs. Buy & Hold** (`qlib/contrib/evaluate_portfolio.py:200-212`, `cov(estratégia, benchmark)/var(benchmark)`): como o painel inferior do HTML já compara a Equity Curve da estratégia com Buy & Hold BTC (`CLAUDE.md` §4), o Beta quantificaria objetivamente o quanto nossa estratégia está reduzindo a exposição ao risco do ativo.

> ⚠️ **Ajuste necessário para cripto:** internamente o Qlib anualiza com `N≈238` (calibrado ao calendário de pregão de ações). Como BTC negocia 365 dias/ano (mercado 24/7), o fator de anualização correto para nós é **N=365**, não 238 nem os 252 tradicionais de renda variável — copiar o `N` do Qlib "as-is" sub/superestimaria o Information Ratio anualizado.

### 🔍 Ideias e Boas Práticas Extraídas do PyPortfolioOpt:
*(Análise concluída em 16/07/2026 — fontes em `/referencias/pyportfolioopt/pypfopt/`, referências no formato arquivo:linha)*

**1. Fórmulas para o relatório final (anualização já ajustada para N=365, regra herdada do bloco Qlib acima):**
- [ ] **Sortino Ratio** — adaptado de `EfficientSemivariance.portfolio_performance()` (`pypfopt/efficient_frontier/efficient_semivariance.py:281-318`). Diferença-chave vs. Information Ratio: o denominador só penaliza retornos abaixo de um MAR (Minimum Acceptable Return; usamos 0), ignorando volatilidade "boa" (upside):
  ```
  desvio_downside_anual = sqrt( Σ [min(r_t − MAR, 0)]² / T × 365 )
  Sortino = (retorno_anualizado − taxa_livre_risco) / desvio_downside_anual
  ```
  > 🛡️ **Guarda (Auditoria da Fase 2.5):** se `desvio_downside == 0` (cenário real: estratégia 100% em caixa no subperíodo → retornos exatamente 0), reportar **N/A** — nunca substituir por epsilon, que geraria Sortinos absurdos ranqueando configurações degeneradas no topo do grid.
- [ ] **Calmar Ratio** — **não existe nativamente no PyPortfolioOpt** (busca por "calmar" no pacote inteiro: zero ocorrências; o parente mais próximo é `EfficientCDaR`, que otimiza por Conditional Drawdown-at-Risk, não pelo Calmar clássico). Aplicamos a fórmula canônica, reaproveitando o **mesmo** `max_drawdown` já adotado do Qlib acima, para manter as duas métricas consistentes entre si:
  ```
  retorno_anualizado = (1 + r).cumprod().iloc[-1] ** (365 / T) − 1
  Calmar = retorno_anualizado / abs(max_drawdown)
  ```
  > 🛡️ **Guardas (Auditoria da Fase 2.5):** (i) `max_drawdown == 0` (equity flat, ex.: sempre em caixa) → **N/A**, nunca dividir; (ii) o sanity check dos dados brutos (`CLAUDE.md` §4: preço > 0, |retorno diário| < 60%) deve rodar **antes** desta fórmula — um retorno ≤ −100% vindo de dado corrompido faria `cumprod() ≤ 0` e a potência fracionária retornaria NaN/complexo. A anualização geométrica é a convenção única de todas as métricas (`CLAUDE.md` §5).

**2. Avaliação: vale a pena um "Freio de Volatilidade" (Target Volatility) na escala de 7 níveis?**
- [x] **Veredito revisado na Auditoria da Fase 2.5: FORA da v1.** O conceito é tecnicamente válido — o PyPortfolioOpt o formaliza em `EfficientFrontier.efficient_risk(target_volatility)` (`pypfopt/efficient_frontier/efficient_frontier.py:359-412`), e adaptado à nossa escala agiria como um multiplicador `min(1, vol_alvo / vol_realizada_30d)` por cima do `w_BTC`. Porém, na auditoria ele foi identificado como o item mais vulnerável do plano perante a banca: adiciona um **segundo mecanismo de risco** por cima do Z-Score (atribuição de performance turva: foi o sinal ou foi o freio?), mais um hiperparâmetro (`vol_alvo`) e inflaria o Grid Search que o protocolo anti-snooping manda encolher. **Decisão:** v1 sem o freio; se explorado no futuro, com `vol_alvo` fixado a priori (fora do grid) e apresentado como estudo de robustez, nunca como parte do motor otimizado (`CLAUDE.md` §3).

  > **Por que isso blindaria contra crashes (em 3 linhas):** (1) volatilidade se agrupa e tende a disparar *antes/durante* quedas fortes, então o freio reage mais rápido que o Z-Score de 90 dias, que é mais lento; (2) ele reduz a exposição a BTC automaticamente quando o mercado fica turbulento, independente do que o Score de valuation/sentimento esteja dizendo naquele momento — uma segunda linha de defesa ortogonal à primeira; (3) por ser só uma razão `vol_alvo/vol_realizada`, é uma regra simples e 100% explicável, coerente com a "Neutralidade de Complexidade" do `CLAUDE.md`.

  > ⚠️ **Ressalva (superada pela decisão acima):** calibrar `vol_alvo` exigiria entrar no mesmo Grid Search In-Sample — exatamente o inchaço de espaço de busca que a Auditoria da Fase 2.5 vetou. Por isso a decisão final é fixá-lo a priori (se um dia for usado), nunca calibrá-lo.

> ⚠️ **Mesma régua de anualização do bloco Qlib:** usar sempre **N=365** nas fórmulas acima — nunca o `frequency=252` default do PyPortfolioOpt, que é calibrado para o calendário de pregão de ações, não para um ativo 24/7 como BTC.

*(Pesquisa da Fase 2 concluída — Qlib + PyPortfolioOpt. Implementação entra na Fase 3, ao programar `backtest.py`. Nenhum arquivo `.py` foi alterado nesta etapa de planejamento.)*

---

## FASE 2.5: Auditoria de Estresse da Arquitetura [CONCLUÍDA em 16/07/2026]
*Auditoria pré-programação nos 4 eixos: data leakage, consistência matemática, data snooping no Grid Search e neutralidade de complexidade. Todas as correções foram incorporadas ao `CLAUDE.md` (§1–§6) e refletidas no checklist da Fase 3.*

- [x] **Warm-up dimensionado (gravidade alta):** o histórico do FNG só existe desde **01/02/2018**; preço baixado desde 2017-01-01 para aquecer a SMA 200; a janela avaliada do In-Sample começa no **primeiro Z-Score válido** (~mai/2018), com `min_periods=90` estrito.
- [x] **Custos de transação e churn (gravidade alta):** 10 bps sobre o valor negociado em cada rebalanceamento; rebalanceio **somente na mudança de nível** da escala; equity reportada com e sem custos (padrão Qlib já extraído na Fase 2).
- [x] **Grid Search blindado contra data snooping (gravidade alta):** espaço reduzido a 4 parâmetros (cortes simétricos ±b1/±b2/±b3 + `Peso_Mayer`, com pesos somando 1); grid grosso; objetivo único **pré-declarado** (Sortino IS, com T+1 e custos dentro do loop); restrição anti-solução-degenerada (exposição média a BTC ≥ 25% no IS); protocolo **one-shot** no OOS; heatmap de robustez na vizinhança do ótimo.
- [x] **Guardas numéricas (gravidade média):** Sortino e Calmar reportam N/A quando o denominador é 0 (nunca epsilon); Z-Score mantém a escala anterior se o std móvel ≈ 0; sanity check dos dados brutos antes de qualquer métrica.
- [x] **Convenção T+1 exata (gravidade média):** `retorno_estratégia[t] = w_sinal[t-2] × r[t]` (sinal no close de D, execução no close de D+1, retorno capturado a partir do candle D+2) — aplicada uniformemente à estratégia, ao Grid Search e ao benchmark Buy & Hold.
- [x] **Definições que faltavam (gravidade média):** direção **contrária** do mapeamento Score_Z → escala (Score_Z alto = sobreaquecido = menos BTC); caixa remunerado a 0%; fronteira IS/OOS pela data do retorno (IS até 31/12/2022 inclusive).
- [x] **Nomenclatura corrigida (gravidade baixa):** o "Information Ratio" do Qlib é, na verdade, um Sharpe com rf=0 — renomeado no relatório.
- [x] **Complexidade cortada:** Freio de Volatilidade **fora da v1** (veredito revisado na Fase 2); relatório limitado a ~6 métricas defendíveis + Beta bônus.
- [x] **Esclarecimento anti-zelo-excessivo:** janela móvel causal que cruza a fronteira IS/OOS olhando para trás é legítima — **não resetar** o rolling em jan/2023.
- [x] **Caveat honesto assumido:** 2018–2022 contém ~1,5 ciclo de BTC; a limitação de observações independentes será reconhecida explicitamente no relatório final.

---

## FASE 3: Programação do Motor Quantitativo (`backtest.py`) [A FAZER]
*Implementar seguindo estritamente as regras dos §2–§6 do `CLAUDE.md` (convenção T+1, warm-up, custos, guardas numéricas e protocolo do Grid Search).*
- [ ] **Extração de dados:** preço BTC-USD desde 2017-01-01 (`yfinance`) + FNG (`Alternative.me`, existe desde 01/02/2018); cache local dos CSVs brutos na primeira captura (point-in-time); preenchimento de FNG faltante com **forward-fill apenas**; sanity check (preço > 0, |retorno diário| < 60%, sem datas duplicadas — abortar em violação).
- [ ] **Sinal:** Score Combinado com `Peso_Mayer + Peso_FNG = 1` e Z-Score móvel `.rolling(90, min_periods=90)` causal, com guarda de std ≈ 0 → mantém escala anterior.
- [ ] **Mapeamento e alocação:** cortes simétricos ±b1/±b2/±b3 em direção contrária (Score_Z alto → menos BTC); `w_BTC = (Escala + 3) / 6`.
- [ ] **Motor de carteira:** convenção T+1 (`retorno[t] = w_sinal[t-2] × r[t]`); rebalanceio só na mudança de nível; custo de 10 bps debitado na execução; caixa a 0%; equity marcada a mercado (`caixa + qtd_BTC × preço`) com e sem custos; warm-up excluído da janela avaliada (estratégia e benchmark começam na mesma data).
- [ ] **Grid Search In-Sample:** 4 parâmetros, grid grosso determinístico; objetivo único pré-declarado = Sortino IS (T+1 + custos dentro do loop); descartar configurações com exposição média < 25% ou métrica N/A; gerar heatmap da vizinhança do ótimo.
- [ ] **Simulação final Out-of-Sample:** execução **one-shot** com parâmetros congelados (sem segunda rodada de tuning); benchmark Buy & Hold com a mesma convenção e data de início; rolling não é resetado na fronteira.

---

## FASE 4: Auditoria Visual e Gráficos (`backtest_resultado.html`) [A FAZER]
- [ ] Programar painel superior do Plotly (Preço + SMA 200 + Setas de Rebalanceamento).
- [ ] Programar painel inferior do Plotly (Equity Curve da estratégia **com e sem custos** vs. Buy & Hold + Área de alocação de caixa).
- [ ] Tabela de métricas (máx. 6 + bônus, `CLAUDE.md` §5): Retorno anualizado, Volatilidade anualizada, Sharpe (rf=0), Sortino, Calmar, Max Drawdown, Beta vs. Buy & Hold — com N/A explícito quando a guarda numérica disparar.
- [ ] Heatmap de robustez do Grid Search (vizinhança do ótimo) como material de defesa perante a banca.
- [ ] Exportar HTML interativo para auditoria e apresentação da banca.