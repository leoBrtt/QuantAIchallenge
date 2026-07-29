# RELATÓRIO TÉCNICO — CONTRAMARÉ (Spot e L/S)
## Motor Quantitativo com Três Indicadores, Validação Out-of-Sample e Análise Crítica

| | |
|---|---|
| **Projeto** | Desafio Quant AI 2026 — Itaú Asset |
| **Estratégia** | CONTRAMARÉ — sinal contrarian único, dois perfis de execução |
| **Mandato Spot** | Fração controlada do risco do BTC (beta ~0,5; drawdown estruturalmente menor) |
| **Mandato L/S** | Retorno absoluto descorrelacionado (beta ~0), sem alavancagem (\|w\| ≤ 1) |
| **Data** | 29/07/2026 (dados até 29/07/2026 — 3.012 dias avaliados) |
| **Protocolo** | `PRE_REGISTRO.md` — 1º commit do repositório (`1191e77a`), anterior a qualquer execução |
| **Reprodução** | `./atualizar.sh --offline` (cache point-in-time em `dados/`) |

---

## 1. Sumário Executivo

Um único sinal contrarian — Z-Score móvel (90d) do Score Combinado de **três
indicadores** — dirige dois perfis de execução no mesmo motor:

| | **CONTRAMARÉ Spot** | **CONTRAMARÉ L/S** |
|---|---|---|
| Parâmetros congelados (IS) | pesos 0,2/0,6/0,2 · cortes ±2,0/±2,5/±3,0 | pesos 0,0/0,2/0,8 · cortes ±0,5/±1,5/±2,0 |
| Sortino IS (grid, caixa 0%) | 0,781 | **−0,309** |
| **OOS (líq., 2023→)** | ret. +31,6% a.a. · Sortino **2,01** · MaxDD −27,7% | ret. +13,4% a.a. · Sortino 0,92 · MaxDD −27,1% |
| B&H BTC spot (OOS, líq.) | ret. +46,1% a.a. · Sortino 1,53 · MaxDD −53,1% | idem |
| Beta vs. B&H (OOS) | 0,52 | 0,09 |

**Veredito honesto, adiantado:** o perfil **Spot é a estratégia**; entrega mais
Sortino, mais Calmar e metade do drawdown do B&H com metade do beta, e é
robusto a custo (Sortino OOS 1,70 mesmo a 50 bps). O perfil **L/S é um estudo
com resultado misto reportado como está**: o melhor ponto do grid In-Sample
teve Sortino *negativo*, e o OOS — executado uma única vez mesmo assim, como
manda o protocolo — mostra um diversificador de crise (ganha em 2022, 2025 e
2026) que não se sustenta como mandato isolado (Seções 7 e 9).

## 2. A Tese: três eixos independentes do mesmo exagero

O mercado de Bitcoin exagera nos dois sentidos. Cada indicador mede o exagero
em um eixo distinto:

1. **Valuation** — Múltiplo de Mayer (preço/SMA200): o preço está esticado?
2. **Sentimento declarado** — Fear & Greed: o que a multidão *diz* sentir.
3. **Posicionamento com dinheiro no risco** — funding rate do perpétuo XBTUSD:
   o que os alavancados *pagam* para manter posição. Funding alto = compra
   alavancada financiando euforia; funding negativo = short pagando para
   apostar na queda, tipicamente perto de fundos.

A independência não é retórica: no In-Sample, corr(funding, FNG) = 0,45 e
corr(funding, Mayer) = 0,43 — enquanto Mayer × FNG correlacionam 0,77 entre
si. **O funding é o eixo mais ortogonal do trio** (gate de redundância
pré-declarado no `PRE_REGISTRO.md`: reprovaria acima de 0,8).

No perfil L/S o funding tem papel duplo, e economicamente elegante: além de
sinal, é **fluxo de caixa da posição** — o short aberto na euforia *recebe* o
funding que os comprados alavancados pagam.

## 3. Dados (point-in-time, cache congelado)

| Série | Fonte | Início | Preenchimento |
|---|---|---|---|
| BTC-USD (close) | yfinance | 2017-01-01 | — |
| Fear & Greed | Alternative.me | 2018-02-01 | ffill |
| Selic anualizada | BCB/SGS 1178 | 2017-01-02 | ffill (dias úteis → corridos) |
| Funding XBTUSD | BitMEX (API pública) | 2016-05-14 | ffill |

- **Funding:** soma diária das 3 liquidações de 8h (00/08/16 UTC). O campo
  `fundingRateDaily` da API (projeção) não é usado. A BitMEX é a única fonte
  gratuita cobrindo todo o IS e era o veículo dominante de perpétuos em
  2018-2019 — escolha point-in-time correta para a janela de treino.
- **Causalidade:** última liquidação do dia D às 16:00 UTC, conhecida no
  fechamento de D; com a convenção T+1 (execução D+1, efeito D+2) a folga é
  ≥ 1 dia inteiro.
- **Sanity checks** (abortam a execução): preço > 0; |retorno| < 60%; Selic ∈
  [0%, 60%]; |funding diário| ≤ 2% (cap BitMEX = 1,125%/dia); datas únicas e
  ordenadas.
- Janela avaliada: **2018-05-01 → 2026-07-29** (primeiro Z-Score válido;
  warm-up excluído para estratégia E benchmark). IS: 1.705 retornos; OOS: 1.306.

## 4. O Motor: um simulador, dois perfis

Convenções comuns (herdadas e auditadas): T+1 único (`retorno[t] =
w_sinal[t-2] × r[t]`); custo de 10 bps sobre o valor negociado no dia da
execução; rebalanceamento só na mudança de nível; equity marcada a mercado dia
a dia; N=365 geométrico; guardas de divisão por zero → N/A.

**Spot:** `w = (escala+3)/6 ∈ [0,1]`; nocional comprado sai do caixa; caixa
rende Selic apenas na simulação final congelada.

**Futuros L/S:** `w = escala/3 ∈ [-1,+1]`; perpétuo **totalmente
colateralizado** (nocional não consome caixa): liquidação diária
(`caixa += contratos × Δpreço`), funding diário sobre a posição
(`caixa −= contratos × preço × funding`, short recebe funding positivo) —
**dentro do motor e do Grid Search**, por ser P&L do instrumento; recap
pré-declarado se exposição efetiva > 1,5 (não disparou nenhuma vez em
nenhuma janela). Alavancagem proibida: |w| alvo ≤ 1.

**Verificação do motor** (anterior à primeira execução do grid, commit
`7dea14d`): 24 configurações reproduzidas exatamente contra um motor de
referência de 2 indicadores com `peso_funding = 0`; perfil futuros com sinal
constante +3 e funding zerado replica byte a byte o B&H spot; identidade
`r_equity[t] = w_exec[t-1] × r_preço[t]` verificada em todos os dias sem
trade do short.

## 5. Protocolo de Otimização e o Segundo Olhar

- **Espaço (fixado a priori):** simplex de pesos passo 0,2 (21) × cortes
  {0,5…3,0}σ passo 0,5σ (20 trincas) = **420 combinações por perfil**.
- **Objetivo único:** Sortino (MAR=0) no IS, custos e T+1 dentro do loop,
  caixa a 0% dentro do loop.
- **Restrição anti-degenerada:** exposição média |w| ≥ 25% no IS.
- **OOS one-shot por perfil**, parâmetros congelados, sem segunda rodada.

**Viés de desenho (declaração obrigatória):** o protocolo acima blinda a
*escolha de parâmetros* contra look-ahead — e o hash do primeiro commit prova
que espaço, objetivo e restrições precederam qualquer resultado. O que nenhum
protocolo elimina é o **viés de desenho**: esta estratégia foi concebida em
2026 por quem conhece a história do BTC até 2026, incluindo o período usado
como OOS — como toda estratégia desenhada hoje, por qualquer equipe. As
afirmações verificáveis são: *os parâmetros foram escolhidos exclusivamente no
In-Sample* e *o OOS foi executado uma única vez para este modelo*.

## 6. Resultados — CONTRAMARÉ Spot

| Métrica (líq.) | IS Estratégia | IS B&H | OOS Estratégia | OOS B&H |
|---|---:|---:|---:|---:|
| Retorno anualizado | +22,93% | +13,29% | **+31,60%** | +46,13% |
| Volatilidade | 35,93% | 70,42% | 24,76% | 46,83% |
| Sharpe (rf=0) | 0,75 | 0,54 | **1,23** | 1,04 |
| Sortino (MAR=0) | 0,95 | 0,27 | **2,01** | 1,53 |
| Calmar | 0,53 | 0,17 | **1,14** | 0,87 |
| Max Drawdown | −43,65% | −76,65% | **−27,71%** | −53,06% |
| Beta vs. B&H | 0,50 | — | 0,52 | — |
| Exposição média | 48,8% | 100% | 51,3% | 100% |
| Rebalanceios | 145 | 1 | 148 | — |

- **Mandato cumprido com folga:** metade do beta, metade do drawdown, e —
  diferentemente do que um mandato defensivo obriga — Sharpe/Sortino/Calmar
  *maiores* que os do ativo em ambas as janelas.
- **Robustez a custo (OOS, caixa Selic):** Sortino 2,01 @ 10 bps → 1,89 @ 25
  bps → **1,70 @ 50 bps** — a vantagem sobre o B&H (1,53) sobrevive a 5× o
  custo assumido.
- **Efeito Selic isolado (OOS @ 10 bps):** com caixa a 0%, ret. +24,0% e
  Sortino 1,51 (≈ empata com B&H em Sortino, ainda com metade do drawdown). A
  vantagem *além* do empate vem do carrego do caixa — ver Limitação 3.
- **Timing vs. dosagem:** benchmark estático 50/50 (mesmo motor, mesma Selic)
  faz Sortino 1,43 no OOS; a estratégia faz 2,01. O timing adiciona valor
  sobre a simples dosagem de risco.
- **Robustez dos parâmetros:** as 5 melhores configurações do grid usam os
  mesmos cortes (±2,0/±2,5/±3,0) com pesos vizinhos — superfície plana no
  topo (`resultados/heatmap_robustez_spot.html`). Zero descartes no grid.
- O peso ótimo do funding (0,2) não é decorativo: a mesma configuração com
  `peso_funding = 0` cai de Sortino IS 0,781 para 0,609.

## 7. Resultados — CONTRAMARÉ L/S (reportado como está)

| Métrica (líq.) | IS Estratégia | OOS Estratégia | OOS B&H |
|---|---:|---:|---:|
| Retorno anualizado | −0,41% | +13,36% | +46,13% |
| Volatilidade | 29,78% | 21,51% | 46,83% |
| Sharpe (rf=0) | 0,13 | 0,69 | 1,04 |
| Sortino (MAR=0) | **−0,02** | 0,92 | 1,53 |
| Max Drawdown | −57,57% | −27,13% | −53,06% |
| Beta vs. B&H | 0,01 | 0,09 | — |
| Exposição média (sinal / \|w\|) | −2,2% / 26,4% | +1,0% / 28,2% | 100% |
| Rebalanceios · recaps | 665 · 0 | 583 · 0 | — |

O que os números dizem, sem maquiagem:

1. **O grid In-Sample não encontrou configuração long/short com Sortino
   positivo** — o melhor ponto válido foi −0,31 (caixa 0%). Short sistemático
   de BTC sangrou mais do que o funding recebido compensou.
2. **Interação restrição × mapeamento (achado de protocolo):** a melhor
   configuração *bruta* do grid L/S era exatamente a do Spot (pesos 0,2/0,6/0,2,
   cortes largos; Sortino 0,57) — mas no mapeamento L/S o nível 0 é *flat*, e
   com cortes largos a carteira fica flat ~90% do tempo → exposição média
   |w| ≈ 10% → **descartada pela restrição pré-declarada de |w| ≥ 25%** (220
   dos 420 pontos do grid L/S caíram nessa regra). A restrição, desenhada para
   impedir o Spot de "vencer escondido no caixa", forçou o L/S para cortes
   estreitos (±0,5σ) com churn alto (665 rebalanceios no IS). Pelo protocolo,
   a regra valia e foi cumprida; o aprendizado fica registrado (Seção 10).
3. **No OOS, o L/S se comporta como diversificador de crise:** anos positivos
   justamente onde o B&H apanha — **+22,6% em 2022 (B&H −64,3%), +12,6% em
   2025 (B&H −6,3%), +5,5% em 2026 (B&H −26,6%)** — e drawdowns de crise
   muito menores (COVID −20,8% vs. −51,9%; FTX −7,7% vs. −25,8%; 2026 −21,2%
   vs. −39,6%). Beta 0,09.
4. **Fragilidade a custo (fatal como mandato isolado):** com 151 rebal./ano, o
   Sortino OOS cai de 0,92 @ 10 bps para 0,16 @ 25 bps e **−0,89 @ 50 bps**.
   E com caixa a 0% @ 10 bps, o retorno OOS é +0,3% a.a. — ou seja, **quase
   todo o retorno líquido do L/S no OOS é o carrego da Selic sobre o
   colateral**, não o sinal. Dito com todas as letras.

## 8. Análise Crítica — Spot (mandato principal)

**Ano a ano (líq., estratégia vs. B&H):** 2018 −31,4/−59,6 · 2019 +53,3/+92,4 ·
2020 +147,1/+303,5 · 2021 +42,5/+59,7 · 2022 −29,2/−64,3 · 2023 +62,3/+155,5 ·
2024 +76,2/+121,1 · **2025 +3,3/−6,3 · 2026 (parcial) −9,6/−26,6**. O padrão é
o do mandato: captura parcial dos bulls, corte de ~metade das quedas — e nos
dois anos ruins do OOS a estratégia protegeu.

**Crises (drawdown na janela):** COVID/2020 −29,9% vs. −51,9%; FTX/2022
−13,5% vs. −25,8%; correção 2026 −18,2% vs. −39,6%.

**IR canônico:** IS −0,29; OOS −0,79 (TE 23,1%; retorno ativo geométrico
−14,5 p.p. a.a.). Negativo e esperado: o mandato é risco controlado, não
retorno ativo — o IR é reportado para não deixar a impressão de que a
estratégia "vence" o BTC em retorno. Não vence; não promete vencer.

**Inércia e whipsaw:** 90% do tempo no nível 0 (50% BTC); 35,5 rebal./ano;
24,9% dos saltos ≥ 2 níveis. Os cortes largos (±2,0σ+) compraram inércia —
um terço dos rebalanceios da geração anterior de cortes estreitos.

**Autópsia dos extremos:** 14 entradas em −3 (venda por euforia): BTC em
média **−3,0% nos 30d seguintes** (o sinal acertou o curto prazo), +28,3% em
180d (vendeu cedo demais — custo declarado do contrarianismo). 16 entradas em
+3 (compra por pânico): +7,8% em 30d e **+51,4% em 180d** — o lado comprador
do sinal é o mais valioso.

## 9. Estudos de Sensibilidade (sinal congelado; não é re-tuning)

Sortino OOS por custo × política de caixa:

| Perfil | 10 bps | 25 bps | 50 bps | 10 bps, caixa 0% |
|---|---:|---:|---:|---:|
| Spot | 2,01 | 1,89 | 1,70 | 1,51 |
| L/S | 0,92 | 0,16 | −0,89 | 0,02 |
| B&H spot (referência) | 1,53 | | | |

## 10. Limitações Declaradas

1. **Viés de desenho** (Seção 5) — declarado, não eliminável, comum a todos os
   participantes; mitigado por pré-registro verificável em git.
2. **Ótimo do Spot na borda do grid em b3** (3,0σ = teto do espaço; b1 e b2
   interiores). O espaço foi fixado a priori; ampliar após ver o OOS seria
   re-tuning. Fica reportado, não corrigido.
3. **Descasamento cambial:** caixa/colateral rende Selic (BRL) enquanto o BTC
   é cotado em USD, sem hedge — infla o resultado líquido (o efeito está
   isolado nas Seções 6, 7 e 9: no Spot a tese sobrevive sem a Selic; no L/S
   não).
4. **Venue única de funding (BitMEX):** dominante em 2018-2019, perdeu
   relevância para a Binance pós-2021 — o funding recente da BitMEX pode
   representar menos o posicionamento agregado do mercado.
5. **Restrição de exposição desenhada para o Spot penalizou o L/S** (Seção 7,
   item 2) — regra simétrica aplicada a mapeamentos assimétricos.
6. **Poucos ciclos independentes:** 2018-2022 ≈ 1,5 ciclo de BTC.
7. **FNG sem metodologia versionada** pelo provedor.
8. **Custo fixo de 10 bps, sem slippage/spread** — estressado até 50 bps na
   Seção 9, não além.

## 11. Conclusão e Próximos Passos

**Demonstrado:** um sinal contrarian de três eixos, pré-registrado e
disciplinado por T+1/custos/one-shot, cumpre no OOS o mandato de fração
controlada de risco (Spot: Sortino 2,01 vs. 1,53, metade do drawdown, beta
0,52) com robustez a custo e superfície de parâmetros plana. O funding rate
agrega valor mensurável ao sinal (+0,17 de Sortino IS vs. o mesmo modelo sem
funding).

**NÃO demonstrado:** que vender BTC a descoberto sistematicamente agregue
valor após custos — o L/S tem Sortino IS negativo e, no OOS, seu retorno
líquido é majoritariamente carrego de Selic. O valor observado do L/S está
concentrado em janelas de crise.

**Próximos passos (cada um exigiria novo pré-registro e um único OOS novo):**
1. Restrição de exposição específica por perfil (ex.: |w| ≥ 25% *quando
   posicionado*, ou piso de participação), desfazendo a distorção da Seção 7.
2. Caixa em taxa USD (T-bill 3m) para eliminar a Limitação 3 — uma variável
   por vez; deliberadamente não misturada a esta rodada.
3. L/S como *overlay* de crise sobre o Spot (short apenas em euforia extrema),
   em vez de mandato contínuo.
4. Funding agregado multi-venue (composto BitMEX/Binance/OKX) para a era
   pós-2021.
5. Hedge cambial explícito do caixa.

## 12. Uso de IA Generativa

Documentado em `USO_DE_IA.md` (critério 4.7), incluindo o papel da IA neste
redesenho e os pontos em que o protocolo restringiu o que a IA podia fazer.

## 13. Artefatos

| Artefato | Conteúdo |
|---|---|
| `PRE_REGISTRO.md` | Protocolo congelado (1º commit, `1191e77a`) |
| `backtest.py` | Motor único (dados → sinais → 2 perfis → grid → OOS) |
| `backtest_spot.html` / `backtest_futuros.html` | Painéis interativos (§7 do CLAUDE.md) |
| `resultados/heatmap_robustez_{perfil}.html` | Superfícies de robustez |
| `resultados/grid_search_is_{perfil}.csv` | 420 combinações por perfil, com descartes e motivos |
| `resultados/parametros_otimos_{perfil}.json` | Parâmetros congelados |
| `resultados/metricas_{perfil}.json` | Métricas IS/OOS |
| `resultados/analise_resultados_{perfil}.json` / `.txt` | Análises da Seção 8-9 |
| `dados/*.csv` | Caches point-in-time congelados |
