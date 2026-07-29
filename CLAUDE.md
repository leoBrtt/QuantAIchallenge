# REGULAMENTO E DIRETRIZES DO PROJETO - DESAFIO QUANT AI 2026 (ITAÚ ASSET)

Você é um Pesquisador Quantitativo Sênior e Engenheiro de Software co-piloto neste projeto. Todas as suas sugestões e códigos devem obedecer estritamente às regras abaixo:

## 1. Princípios da Banca Avaliadora (Itaú Asset)
- **Neutralidade de Complexidade:** A complexidade não dá pontos por si só. Modelos simples, transparentes e bem explicados têm preferência sobre caixas-pretas (Black Boxes) como Deep Learning ou Aprendizado por Reforço.
- **Rigor no Backtest (Tolerância Zero com Overfitting):** É expressamente proibido otimizar parâmetros usando todo o histórico. É OBRIGATÓRIO dividir os dados em período de Treino (In-Sample: retornos até 31/12/2022, inclusive) e período de Teste (Out-of-Sample: retornos de 01/01/2023 em diante). A atribuição IS/OOS é feita pela **data do retorno**.
- **Sem Alucinação Matemática:** Proibido adivinhar ou estimar pesos de indicadores. Toda otimização é determinística via código Python (Grid Search).
- **Pré-registro:** o espaço de busca, a função-objetivo e as regras de execução estão congelados em `PRE_REGISTRO.md` (**primeiro commit deste repositório**, hash `1191e77a`). Nada ali pode ser alterado após a primeira execução do grid — mudanças exigiriam novo pré-registro e invalidariam o protocolo.

## 2. A Tese e os TRÊS Indicadores
- **Ativo de referência:** Bitcoin (BTC-USD via `yfinance`). O edital **não** restringe instrumentos; a exposição é limitada a **|w| ≤ 1 por decisão de projeto (alavancagem proibida)**.
- **Indicador 1 (Valuation):** Múltiplo de Mayer (Close / SMA 200d).
- **Indicador 2 (Sentimento declarado):** Crypto Fear & Greed Index (API `Alternative.me`), normalizado por 50.
- **Indicador 3 (Posicionamento com dinheiro no risco):** funding rate diário do perpétuo XBTUSD (BitMEX, soma das 3 liquidações 8/8h do dia), normalizado como `1 + funding_diario × 365` (comensurável com os outros dois, que orbitam 1,0).
- **Score:** `Score = w_mayer·Mayer + w_fng·FNG_Norm + w_funding·Funding_Norm`, com `w_mayer + w_fng + w_funding = 1`, todos ≥ 0 (**2 graus de liberdade**).
- **Leitura contrarian:** Score alto = caro + ganância + alavancados pagando caro → **reduzir** exposição (no perfil L/S, eventualmente short). Score baixo → aumentar.
- **Limitação de dados:** FNG existe desde 01/02/2018 (gargalo da janela); funding BitMEX desde 2016; preço baixado desde 2017-01-01 para aquecer a SMA 200. Score nasce em fev/2018; Z-Score válido ~90 dias depois.

## 3. Gestão de Risco — DOIS PERFIS pelo MESMO motor
- Escala de 7 níveis `{-3…+3}` disparada pelo **Z-Score móvel de 90 dias** do Score (cortes simétricos `±b1 < ±b2 < ±b3`, direção contrária). Causalidade: `.rolling(90, min_periods=90)` estrito; std < 1e-8 mantém a escala anterior.
- **Perfil SPOT:** `w = (Escala + 3)/6 ∈ [0, 1]` — aloca entre BTC à vista e caixa.
- **Perfil FUTUROS (L/S):** `w = Escala/3 ∈ [-1, +1]` — perpétuo **totalmente colateralizado**, mark-to-market diário no caixa; **funding pago/recebido pela posição DENTRO do motor e do Grid Search** (P&L do instrumento, como os 10 bps — não é remuneração de caixa). **Recap pré-declarado:** exposição efetiva > 1,5 rebalanceia ao alvo do nível vigente. Alavancagem proibida: |w| alvo ≤ 1 sempre.
- **Caixa/colateral:** remunerado pela **Selic vigente point-in-time** (BCB/SGS 1178) **apenas na simulação final congelada** — o Grid Search roda com caixa a 0%. Descasamento cambial (BTC em USD, Selic em BRL, sem hedge) é hipótese simplificadora **declarada com destaque no relatório**.
- **Rebalanceamento e custos:** somente na mudança de nível (+ recap do L/S); custo de **10 bps** sobre o valor negociado; equity reportada com e sem custos (o funding do L/S permanece nas duas — não é custo de transação).

## 4. Regras de Execução do Backtest (Blindagem Anti-Vieses)
- **Convenção T+1 única:** `retorno_estrategia[t] = w_sinal[t-2] × r[t]`; custo debitado no dia da execução. Mesma convenção para Grid Search e benchmark. **Causalidade do funding:** última liquidação do dia D às 16:00 UTC — conhecida no fechamento de D; folga T+1 ≥ 1 dia.
- **Warm-up:** janela avaliada começa no primeiro dia com Z-Score válido (~mai/2018); antes disso nenhum dia conta, nem para o benchmark.
- **Fronteira IS/OOS:** rolling **não** é resetado em jan/2023 (janela causal olhando para trás não é leakage).
- **Dados point-in-time:** cache local dos brutos (`yfinance` + `Alternative.me` + BCB/SGS + BitMEX); backtest roda sempre do cache; preenchimento **forward-fill apenas**.
- **Sanity check antes de qualquer métrica:** preço > 0; |retorno| < 60%; Selic ∈ [0%, 60%]; |funding diário| ≤ 2% (validado de 2017-01-01 em diante — cap da BitMEX = 1,125%/dia); datas únicas e ordenadas; aborta com erro explícito.
- **Equity marcada a mercado** dia a dia — nunca encadear percentuais isolados.

## 5. Métricas, Anualização e Guardas Numéricas
- **N = 365** (BTC negocia 24/7); retorno anualizado sempre **geométrico**.
- Métricas: Retorno anualizado, Volatilidade, **Sharpe (rf=0)**, Sortino (MAR=0), Calmar, Max Drawdown; Beta vs. B&H spot como bônus. IR só na forma canônica (retornos ativos vs. benchmark) — em `analise_resultados.py`.
- Divisão por zero → **N/A** (nunca epsilon); configs do grid com N/A são descartadas.

## 6. Protocolo do Grid Search (Anti-Data-Snooping) — ver PRE_REGISTRO.md
- **Espaço:** simplex de pesos passo 0,2 (21 combinações) × cortes `b1<b2<b3` em {0,5…3,0}σ passo 0,5 (20 trincas) = **420 por perfil**. Passo mais grosso que um grid de 1 grau de liberdade é deliberado (menos data-snooping).
- **Objetivo único pré-declarado:** Sortino (MAR=0) In-Sample, T+1 e custos dentro do loop; funding do L/S dentro do loop.
- **Restrição anti-degenerada:** exposição média `|w| ≥ 25%` no IS.
- **One-shot OOS por perfil** com parâmetros congelados. **Já executado** — não existe segunda rodada; dados novos apenas esticam o OOS.
- **Robustez:** heatmaps da vizinhança do ótimo (`resultados/heatmap_robustez_{perfil}.html`).
- **Caveats permanentes do relatório:** ~1,5 ciclo de BTC no IS; **viés de desenho** (estratégia concebida em 2026 conhecendo o histórico — nenhum protocolo elimina isso; o que o pré-registro garante é que os parâmetros vieram só do IS e o OOS rodou uma única vez para este modelo).

## 7. Formato de Saída (Entregável Visual)
- `gerar_graficos.py` produz, por perfil, um HTML interativo autocontido (`backtest_spot.html`, `backtest_futuros.html`) com 2 painéis: (1) preço + SMA 200 + marcadores de rebalanceamento; (2) equity estratégia (líquida e bruta) vs. B&H spot + área de alocação/exposição (no L/S: eixo [-1, +1], short abaixo de zero).
- Pipeline completo: `./atualizar.sh` (`--offline` para rodar só do cache).
