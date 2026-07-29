# PRÉ-REGISTRO — CONTRAMARÉ (Spot e L/S) — Desafio Quant AI 2026

**Data:** 29/07/2026. Este documento é commitado **antes** de qualquer execução do
Grid Search ou do Out-of-Sample deste projeto. O hash do commit é a evidência de
que todo o espaço de busca, a função-objetivo e as regras de execução foram
fixados a priori — nada abaixo foi escolhido após observar resultados do grid
ou do OOS deste modelo.

## 1. Tese (três eixos, um sinal contrarian)

O mercado de Bitcoin exagera nos dois sentidos. Medimos o exagero em três eixos
**independentes por construção**:

| Eixo | Indicador | O que mede |
|---|---|---|
| Valuation | Múltiplo de Mayer (Close/SMA200) | preço esticado vs. tendência |
| Sentimento declarado | Fear & Greed Index (Alternative.me) / 50 | o que a multidão *diz* sentir |
| Posicionamento com dinheiro no risco | Funding rate de perpétuos (BitMEX XBTUSD) | o que os alavancados *pagam* para manter posição |

Funding alto = comprados alavancados pagando caro = euforia financiada →
**reduzir** exposição (e, no perfil L/S, eventualmente vender a descoberto —
posição que *recebe* o funding enquanto o exagero persiste). Direção contrarian
idêntica à dos outros dois indicadores, sem inversão de sinal.

**Gate de redundância (medido no IS antes deste registro, critério: corr > 0,8
reprova):** corr(funding_norm, fng_norm) = 0,45 em níveis / 0,52 em z-90d;
corr(funding_norm, mayer) = 0,43 / 0,49. O funding é o eixo mais ortogonal do
trio (Mayer × FNG correlacionam 0,77 entre si). Aprovado.

## 2. Dados do novo indicador

- **Fonte:** BitMEX XBTUSD, API pública `/api/v1/funding` (liquidações 8/8h:
  00/08/16 UTC). Única fonte gratuita que cobre todo o In-Sample
  (histórico desde 2016; Binance só a partir de set/2019). Em 2018–2019 a
  BitMEX era o veículo dominante de perpétuos — escolha point-in-time correta
  para a janela de treino.
- **Agregação diária:** soma dos 3 `fundingRate` liquidados no dia (UTC).
  O campo `fundingRateDaily` da API (projeção) não é usado.
- **Causalidade:** a última liquidação do dia D ocorre 16:00 UTC → conhecida no
  fechamento de D. Com a convenção T+1 (execução em D+1, efeito em D+2), a
  folga causal é ≥ 1 dia inteiro.
- **Preenchimento:** reindex no calendário do preço com forward-fill apenas
  (mesma regra de FNG e Selic). Cache point-in-time congelado em
  `dados/funding_raw.csv`.
- **Sanidade (aborta em violação):** |funding diário| ≤ 2% (cap da BitMEX:
  0,375%/8h → máx. teórico 1,125%/dia; margem para mudança de cap).

## 3. Sinal

```
funding_norm = 1 + funding_diario × 365          (comensurável: Mayer e FNG/50 orbitam 1,0)
score        = w_mayer·mayer + w_fng·fng_norm + w_funding·funding_norm
               com w_mayer + w_fng + w_funding = 1, todos ≥ 0  (2 graus de liberdade)
```

Z-Score móvel de 90 dias do score (causal, `min_periods=90`, guarda de
std < 1e-8 → mantém escala), cortes simétricos ±b1/±b2/±b3 em direção
contrária, escala de 7 níveis {−3…+3} — tudo idêntico à especificação herdada.

## 4. Dois perfis de execução (mesmo sinal, mesmo motor)

| | **CONTRAMARÉ Spot** | **CONTRAMARÉ L/S (futuros)** |
|---|---|---|
| Instrumento | BTC à vista | perpétuo XBTUSD, totalmente colateralizado |
| Mapeamento | `w = (escala+3)/6 ∈ [0, 1]` | `w = escala/3 ∈ [−1, +1]` |
| Escala −3 | 100% caixa | 100% short |
| Alavancagem | — | **proibida: |w| ≤ 1 sempre** |
| Funding | não paga/recebe | P&L diário: `−contratos × preço × funding_d` (short recebe funding positivo) |
| Liquidação | — | mark-to-market diário no caixa |

Regras comuns: T+1; custo 10 bps sobre |Δnocional| no dia da execução;
rebalanceamento só em mudança de nível; equity marcada a mercado; N=365.

**Regra de recap (L/S, fixada aqui, fora do grid):** se a exposição efetiva
`|contratos×preço|/equity` ultrapassar **1,5**, rebalanceia de volta ao alvo
mesmo sem mudança de escala. Válvula de segurança contra deriva após perdas;
o número de disparos será reportado.

## 5. Grid Search (idêntico para os dois perfis, rodado de forma independente)

- **Pesos:** simplex passo 0,2 → 21 combinações `(w_mayer, w_fng, w_funding)`.
- **Cortes:** `b1 < b2 < b3` em {0,5; 1,0; 1,5; 2,0; 2,5; 3,0}σ → C(6,3) = 20.
- **Total: 420 combinações por perfil.** Passo deliberadamente mais grosso que
  um grid de 2 indicadores (um grau de liberdade a mais com passo fino
  explodiria a contagem; grid grosso = menos data-snooping). Teto de 3,0σ
  escolhido a priori pelas caudas pesadas de cripto.
- **Função-objetivo única e pré-declarada:** **Sortino (MAR=0) no In-Sample**
  (retornos até 31/12/2022, atribuição pela data do retorno), com T+1 e custos
  dentro do loop; caixa a 0% dentro do loop; funding do perfil L/S **sempre**
  dentro do loop (custo intrínseco do instrumento, como os 10 bps).
- **Restrição anti-degenerada:** exposição média ≥ 25% no IS — Spot:
  `média(w) ≥ 0,25`; L/S: `média(|w|) ≥ 0,25`. Config com métrica N/A é
  descartada. Desempate determinístico pela ordem de varredura.
- **Robustez:** vizinhança do ótimo (±0,2 em cada peso; ±0,5σ em cada corte)
  reportada em heatmap.

## 6. Out-of-Sample

Retornos de 01/01/2023 em diante. **Uma única execução por perfil, com os
parâmetros congelados pelo grid IS.** Não haverá segunda rodada de tuning após
observar o OOS deste modelo. Benchmark primário: Buy & Hold BTC spot pelo
mesmo motor (escala constante +3); os dois perfis também são comparados entre si.
O rolling de 90d não é resetado na fronteira (janela causal olhando para trás).
Na simulação final congelada (e apenas nela), o caixa/colateral rende a Selic
point-in-time — mesma convenção e mesmo caveat cambial declarado do motor herdado.

## 7. Caveat de viés de desenho (declarado a priori)

O protocolo IS/OOS acima blinda a **escolha de parâmetros** contra look-ahead.
Ele não elimina — e nenhum protocolo elimina — o **viés de desenho**: esta
estratégia foi concebida em 2026 por quem conhece a história do Bitcoin até
2026, incluindo o período usado como OOS. Isso vale para qualquer estratégia
desenhada hoje, por qualquer equipe. O que este pré-registro garante, e é
verificável pelo hash do commit, é que **os parâmetros deste modelo foram
escolhidos exclusivamente no In-Sample e o OOS foi executado uma única vez
para este modelo** — e que espaço de busca, objetivo e restrições não foram
ajustados depois de ver resultado nenhum.
