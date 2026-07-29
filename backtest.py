# -*- coding: utf-8 -*-
"""
MOTOR QUANTITATIVO — CONTRAMARÉ (Spot e L/S) — Desafio Quant AI 2026 (Itaú Asset)
=================================================================================
Estratégia contrarian dirigida pelo Z-Score móvel (90d) do Score Combinado de
TRÊS indicadores — Múltiplo de Mayer (valuation), Fear & Greed Index (sentimento
declarado) e funding rate de perpétuos BitMEX XBTUSD (posicionamento alavancado
com dinheiro no risco) — executada em DOIS perfis pelo MESMO motor:

  - SPOT:    alocação BTC/Caixa em 7 níveis, w = (escala+3)/6 ∈ [0, 1].
  - FUTUROS: perpétuo long/short totalmente colateralizado, w = escala/3
             ∈ [-1, +1] (alavancagem PROIBIDA: |w| <= 1 sempre), mark-to-market
             diário no caixa e funding pago/recebido DENTRO do motor (custo
             intrínseco do instrumento — short recebe funding positivo).
             Recap pré-declarado: exposição efetiva > 1,5 rebalanceia ao alvo.

Espaço de busca, objetivo e regras congelados a priori em PRE_REGISTRO.md
(primeiro commit deste repositório — nada foi ajustado após ver resultados).

Regras de blindagem implementadas (CLAUDE.md §2–§6):
  - Dados point-in-time: cache local dos CSVs brutos; forward-fill apenas no
    FNG, na Selic e no funding (dias sem publicação).
  - Sanity check dos dados brutos ANTES de qualquer métrica (aborta em violação).
  - Convenção T+1 única: retorno_estrategia[t] = w_sinal[t-2] * r[t]
    (sinal no close de D -> execução no close de D+1 -> captura a partir de D+2);
    custo de 10 bps debitado no dia da execução. Mesma convenção para o benchmark.
    Funding: última liquidação do dia D às 16:00 UTC — conhecida no close de D;
    a folga causal da convenção T+1 é >= 1 dia inteiro.
  - Warm-up: janela avaliada começa no primeiro dia com Z-Score válido (~mai/2018,
    gargalo continua sendo o FNG — o funding existe desde 2016);
    antes disso nenhum dia conta — nem para a estratégia, nem para o Buy & Hold.
  - Z-Score estritamente causal: .rolling(90, min_periods=90); std < 1e-8 mantém
    a escala anterior (nunca divide por ~zero).
  - Rebalanceamento somente na mudança de nível da escala (mais o recap do perfil
    futuros, pré-declarado e reportado); equity marcada a mercado, com e sem custos.
  - Caixa/colateral remunerado pela Selic vigente no dia (SGS/BCB 1178,
    point-in-time, capitalização diária) — só na simulação final congelada
    (Módulo 6); o Grid Search (Módulo 5) roda com caixa a 0%. O funding do perfil
    futuros entra SEMPRE (grid incluso): é P&L do instrumento, não remuneração.
  - Grid Search só no In-Sample (retornos até 31/12/2022); objetivo único
    pré-declarado = Sortino (MAR=0) com T+1 e custos dentro do loop; restrição
    de exposição média |w| >= 25%; métricas N/A descartam a configuração.
  - Out-of-Sample one-shot POR PERFIL com parâmetros congelados; rolling NÃO é
    resetado na fronteira de jan/2023 (janela causal olhando para trás).
  - Anualização única N=365 (BTC negocia 24/7); retorno anualizado geométrico.

Saídas (consumidas pela análise / Plotly), sufixadas por perfil:
  dados/{btc_usd,fng,selic,funding}_raw.csv          (cache point-in-time)
  resultados/serie_backtest_{perfil}.csv             (série diária consolidada)
  resultados/grid_search_is_{perfil}.csv             (superfície p/ heatmap)
  resultados/parametros_otimos_{perfil}.json         (parâmetros congelados)
  resultados/metricas_{perfil}.json                  (métricas IS/OOS)
"""

from __future__ import annotations

import itertools
import json
import os

import numpy as np
import pandas as pd
import requests

# ============================================================================
# CONFIGURAÇÃO (todas as convenções pré-declaradas — nada é decidido em runtime)
# ============================================================================
DIR_DADOS = "dados"
DIR_RESULTADOS = "resultados"
CACHE_BTC = os.path.join(DIR_DADOS, "btc_usd_raw.csv")
CACHE_FNG = os.path.join(DIR_DADOS, "fng_raw.csv")
CACHE_SELIC = os.path.join(DIR_DADOS, "selic_raw.csv")
CACHE_FUNDING = os.path.join(DIR_DADOS, "funding_raw.csv")
SERIE_BCB_SELIC = 1178              # SGS/BCB: "Taxa de juros - Selic anualizada base 252"

DATA_INICIO_PRECO = "2017-01-01"   # warm-up da SMA 200 (FNG só existe de 2018-02-01)
FIM_IN_SAMPLE = pd.Timestamp("2022-12-31")   # IS/OOS atribuído pela data do retorno
JANELA_SMA = 200
JANELA_Z = 90
GUARDA_STD = 1e-8                  # std móvel abaixo disso -> mantém escala anterior
CUSTO_TAXA = 0.001                 # 10 bps sobre o valor negociado, no dia da execução
N_ANUALIZACAO = 365                # BTC negocia 24/7 — nunca 252/238
LIMITE_RETORNO_DIARIO = 0.60       # sanity check: |r| >= 60% aborta
LIMITE_SELIC_AA = 0.60             # sanity check: Selic >= 60% a.a. aborta (dado corrompido)
LIMITE_FUNDING_DIA = 0.02          # sanity check: cap BitMEX = 0,375%/8h -> máx. 1,125%/dia

# Grid grosso e determinístico (PRE_REGISTRO §5): 2 graus de liberdade nos pesos
# (simplex passo 0,2 -> 21 combinações) x 20 trincas de cortes = 420 por perfil.
GRID_PESOS = [(m / 5.0, f / 5.0) for m in range(6) for f in range(6 - m)]
GRID_CORTES = np.round(np.arange(0.5, 3.0001, 0.5), 2)              # passo 0,5σ até 3σ
EXPOSICAO_MINIMA_IS = 0.25         # restrição anti-solução-degenerada (média de |w|)

PERFIS = ("spot", "futuros")
RECAP_LIMITE = 1.5                 # futuros: |exposição efetiva| > 1,5 -> recap ao alvo
ESCALA_BUY_HOLD = 3                # +3 => w = 100% BTC spot (benchmark, mesmo motor)


# ============================================================================
# MÓDULO 1 — DADOS E CACHE (point-in-time, anti-leakage)
# ============================================================================
def _mesclar_com_cache(novo: pd.DataFrame, caminho: str) -> pd.DataFrame:
    """
    Atualização do cache point-in-time sem reescrever história: valores já
    congelados sempre prevalecem sobre o download novo; este só anexa datas
    novas e preenche datas que faltavam no cache (lacunas do provedor). Exceção
    única: o último candle cacheado, possivelmente parcial (BTC negocia 24/7),
    é substituído pela versão fechada.
    """
    if not os.path.exists(caminho):
        return novo
    antigo = pd.read_csv(caminho, index_col="Date", parse_dates=True)
    congelado = antigo.iloc[:-1]
    return congelado.combine_first(novo).sort_index()[antigo.columns]


def baixar_btc() -> None:
    """Baixa BTC-USD diário e congela o CSV bruto (só roda se não houver cache)."""
    import yfinance as yf

    df = yf.download("BTC-USD", start=DATA_INICIO_PRECO, progress=False,
                     auto_adjust=True)
    if df is None or df.empty:
        raise ValueError("Download do BTC-USD via yfinance retornou vazio.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df.index.name = "Date"
    _mesclar_com_cache(df, CACHE_BTC).to_csv(CACHE_BTC)


def baixar_fng() -> None:
    """Baixa o histórico completo do Fear & Greed e congela o CSV bruto."""
    resp = requests.get("https://api.alternative.me/fng/",
                        params={"limit": 0, "format": "json"}, timeout=60)
    resp.raise_for_status()
    registros = resp.json()["data"]
    df = pd.DataFrame({
        "Date": pd.to_datetime(pd.to_numeric([r["timestamp"] for r in registros]),
                               unit="s").normalize(),
        "fng": pd.to_numeric([r["value"] for r in registros]),
        "classificacao": [r.get("value_classification", "") for r in registros],
    }).sort_values("Date").set_index("Date")
    if df.empty:
        raise ValueError("Download do FNG via Alternative.me retornou vazio.")
    _mesclar_com_cache(df, CACHE_FNG).to_csv(CACHE_FNG)


def baixar_selic() -> None:
    """Baixa a série histórica da Selic anualizada (SGS/BCB série 1178) e
    congela o CSV bruto. Fonte oficial e pública (Banco Central do Brasil),
    já em % a.a. — dispensa conversão de taxa diária para anual."""
    resp = requests.get(
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{SERIE_BCB_SELIC}/dados",
        params={"formato": "json", "dataInicial": "01/01/2017"}, timeout=60)
    resp.raise_for_status()
    registros = resp.json()
    df = pd.DataFrame({
        "Date": pd.to_datetime([r["data"] for r in registros], format="%d/%m/%Y"),
        "selic_aa": pd.to_numeric([r["valor"] for r in registros]) / 100.0,
    }).sort_values("Date").set_index("Date")
    if df.empty:
        raise ValueError("Download da Selic via BCB/SGS retornou vazio.")
    _mesclar_com_cache(df, CACHE_SELIC).to_csv(CACHE_SELIC)


def baixar_funding() -> None:
    """Baixa o histórico completo de funding do perpétuo XBTUSD (BitMEX, API
    pública, liquidações 8/8h em 00/08/16 UTC) e congela o agregado DIÁRIO.

    Agregação = SOMA dos 3 `fundingRate` liquidados no dia (UTC). O campo
    `fundingRateDaily` da API não é usado: é projeção (taxa de 8h x 3), não o
    funding realizado do dia. Causalidade: a última liquidação do dia D ocorre
    às 16:00 UTC, conhecida no fechamento de D — com a convenção T+1 a folga é
    >= 1 dia inteiro. Fonte escolhida por ser a única gratuita que cobre todo o
    In-Sample (desde 2016; Binance só a partir de set/2019) e por a BitMEX ser
    o veículo dominante de perpétuos em 2018-2019 (escolha point-in-time).
    """
    import time

    registros: list[dict] = []
    start = 0
    while True:
        resp = requests.get("https://www.bitmex.com/api/v1/funding",
                            params={"symbol": "XBTUSD", "count": 500,
                                    "start": start, "reverse": "false"},
                            timeout=60)
        if resp.status_code == 429:               # rate limit público
            time.sleep(int(resp.headers.get("Retry-After", "5")))
            continue
        resp.raise_for_status()
        lote = resp.json()
        if not lote:
            break
        registros.extend(lote)
        start += len(lote)
        time.sleep(1.2)                            # cortesia sob o limite público
    if not registros:
        raise ValueError("Download do funding via BitMEX retornou vazio.")
    bruto = pd.DataFrame({
        "ts": pd.to_datetime([r["timestamp"] for r in registros]),
        "funding_8h": pd.to_numeric([r["fundingRate"] for r in registros]),
    })
    diario = (bruto.set_index("ts")["funding_8h"]
                   .groupby(pd.Grouper(freq="D")).sum(min_count=1).dropna())
    diario.index = diario.index.tz_localize(None).normalize()
    diario.index.name = "Date"
    _mesclar_com_cache(diario.to_frame("funding_d"), CACHE_FUNDING).to_csv(CACHE_FUNDING)


def sanity_check(close: pd.Series, fng: pd.Series, selic: pd.Series,
                 funding: pd.Series) -> None:
    """Aborta com erro explícito em dado corrompido — roda ANTES de qualquer métrica."""
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError("SANITY: datas de preço duplicadas ou fora de ordem.")
    if (close <= 0).any():
        raise ValueError("SANITY: preço de fechamento <= 0 detectado.")
    r = close.pct_change().dropna()
    if (r.abs() >= LIMITE_RETORNO_DIARIO).any():
        piores = r[r.abs() >= LIMITE_RETORNO_DIARIO]
        raise ValueError(f"SANITY: |retorno diário| >= 60% em {list(piores.index.date)}.")
    fng_bruto = fng.dropna()
    if not fng_bruto.index.is_unique or not fng_bruto.index.is_monotonic_increasing:
        raise ValueError("SANITY: datas de FNG duplicadas ou fora de ordem.")
    if ((fng_bruto < 0) | (fng_bruto > 100)).any():
        raise ValueError("SANITY: FNG fora do intervalo [0, 100].")
    selic_bruta = selic.dropna()
    if not selic_bruta.index.is_unique or not selic_bruta.index.is_monotonic_increasing:
        raise ValueError("SANITY: datas de Selic duplicadas ou fora de ordem.")
    if ((selic_bruta < 0) | (selic_bruta >= LIMITE_SELIC_AA)).any():
        raise ValueError(f"SANITY: Selic fora do intervalo [0%, {LIMITE_SELIC_AA:.0%}] a.a.")
    funding_bruto = funding.dropna()
    if not funding_bruto.index.is_unique or not funding_bruto.index.is_monotonic_increasing:
        raise ValueError("SANITY: datas de funding duplicadas ou fora de ordem.")
    # O cap de 0,375%/8h da BitMEX vale para o período que o backtest pode
    # tocar (calendário de preço, 2017+); registros de 2016 no bruto antecedem
    # o cap e ficam fora da validação (e de qualquer janela avaliada).
    funding_janela = funding_bruto[funding_bruto.index >= pd.Timestamp(DATA_INICIO_PRECO)]
    if (funding_janela.abs() > LIMITE_FUNDING_DIA).any():
        raise ValueError(f"SANITY: |funding diário| > {LIMITE_FUNDING_DIA:.0%} "
                         "(cap da BitMEX = 1,125%/dia) — dado corrompido.")


def carregar_dados(atualizar: bool = False) -> pd.DataFrame:
    """Garante o cache, valida os brutos e devolve o painel diário alinhado.

    Com atualizar=True, baixa os dados de novo e anexa apenas as datas novas ao
    cache (o histórico já congelado permanece intacto — ver _mesclar_com_cache).
    """
    os.makedirs(DIR_DADOS, exist_ok=True)
    if atualizar or not os.path.exists(CACHE_BTC):
        baixar_btc()
    if atualizar or not os.path.exists(CACHE_FNG):
        baixar_fng()
    if atualizar or not os.path.exists(CACHE_SELIC):
        baixar_selic()
    if atualizar or not os.path.exists(CACHE_FUNDING):
        baixar_funding()

    btc = pd.read_csv(CACHE_BTC, index_col="Date", parse_dates=True)
    fng = pd.read_csv(CACHE_FNG, index_col="Date", parse_dates=True)
    selic = pd.read_csv(CACHE_SELIC, index_col="Date", parse_dates=True)
    funding = pd.read_csv(CACHE_FUNDING, index_col="Date", parse_dates=True)

    dados = pd.DataFrame({"close": btc["Close"]})
    # Reindexação no calendário do preço + forward-fill APENAS (bfill/interpolação
    # usariam informação do futuro — look-ahead). Antes de 2018-02-01 o FNG fica NaN.
    dados["fng"] = fng["fng"].reindex(dados.index).ffill()
    # Selic: publicação do BCB só em dias úteis; forward-fill cobre fins de
    # semana/feriados com a última taxa vigente (mesma regra anti-leakage do
    # FNG). O 1º dia da série de preço (2017-01-01, feriado) fica sem taxa
    # anterior para repetir — fica NaN e a carteira simplesmente não rende
    # juros nesse dia isolado, muito antes da janela avaliada (~mai/2018).
    dados["selic_aa"] = selic["selic_aa"].reindex(dados.index).ffill()
    # Funding: existe desde 2016 (antes do início da série de preço), logo nunca
    # é NaN no calendário avaliado; ffill cobre eventuais dias sem liquidação.
    dados["funding_d"] = funding["funding_d"].reindex(dados.index).ffill()

    sanity_check(dados["close"], fng["fng"], selic["selic_aa"], funding["funding_d"])
    return dados


# ============================================================================
# MÓDULO 2 — SINAIS: Mayer, FNG, funding, Score, Z-Score causal, escala
# ============================================================================
def calcular_sinais(dados: pd.DataFrame, peso_mayer: float,
                    peso_fng: float) -> pd.DataFrame:
    """Score Combinado de TRÊS indicadores e Z-Score móvel de 90 dias, causais.

    peso_funding = 1 - peso_mayer - peso_fng (simplex: 2 graus de liberdade).
    funding_norm = 1 + funding_diário x 365 — anualizado e centrado em 1 para
    ficar comensurável com o Mayer (preço/SMA200) e o FNG/50, que orbitam 1,0.
    Direção já contrarian sem inversão: funding alto = comprados alavancados
    pagando caro para manter posição = euforia financiada -> Score sobe ->
    menos BTC (e eventualmente short, no perfil futuros).
    """
    peso_funding = 1.0 - peso_mayer - peso_fng
    df = dados.copy()
    df["sma200"] = df["close"].rolling(JANELA_SMA, min_periods=JANELA_SMA).mean()
    df["mayer"] = df["close"] / df["sma200"]
    df["fng_norm"] = df["fng"] / 50.0
    df["funding_norm"] = 1.0 + df["funding_d"] * float(N_ANUALIZACAO)

    # NaN propaga: mesmo com peso 0 em um indicador, o Score só nasce quando os
    # TRÊS existem — o gargalo continua sendo o FNG (2018-02-01), pois o funding
    # existe desde 2016. Janela de avaliação idêntica p/ todo o grid.
    df["score"] = (peso_mayer * df["mayer"] + peso_fng * df["fng_norm"]
                   + peso_funding * df["funding_norm"])

    media = df["score"].rolling(JANELA_Z, min_periods=JANELA_Z).mean()
    std = df["score"].rolling(JANELA_Z, min_periods=JANELA_Z).std()
    z = (df["score"] - media) / std
    z[std < GUARDA_STD] = np.nan   # guarda §3: nunca dividir por ~zero
    df["score_z"] = z
    return df


def mapear_escala(score_z: pd.Series, b1: float, b2: float, b3: float) -> pd.Series:
    """
    Cortes simétricos ±b1/±b2/±b3 em direção CONTRÁRIA (Score_Z alto = mercado
    sobreaquecido = menos BTC). Dias com Z inválido (warm-up ou guarda de std)
    mantêm a escala anterior via forward-fill.
    """
    z = score_z.to_numpy()
    escala = np.select(
        [z >= b3, z >= b2, z >= b1, z > -b1, z > -b2, z > -b3],
        [-3, -2, -1, 0, 1, 2],
        default=3,                         # z <= -b3 -> máximo de BTC
    ).astype(float)
    escala[np.isnan(z)] = np.nan           # np.select trataria NaN como default
    return pd.Series(escala, index=score_z.index).ffill()


# ============================================================================
# MÓDULO 3 — MOTOR DE CARTEIRA (T+1, custos, equity marcada a mercado, 2 perfis)
# ============================================================================
def simular_carteira(close: pd.Series, escala_sinal: pd.Series,
                     custo_taxa: float, perfil: str = "spot",
                     selic_aa: pd.Series | None = None,
                     funding: pd.Series | None = None) -> pd.DataFrame:
    """
    Simula a carteira na janela avaliada (1º índice = primeiro dia com sinal
    válido). Convenção T+1 do §4: o sinal do fechamento de D é executado no
    fechamento de D+1 (custo debitado nesse dia) e o peso novo captura retornos
    a partir de D+2 — equivalente a retorno[t] = w_sinal[t-2] * r[t].

    Loop explícito (e não encadeamento de percentuais) porque a equity é
    marcada a mercado e recalculada a cada rebalanceamento (§4). Rebalanceia
    SOMENTE quando a escala muda de nível (mais o recap do perfil futuros).

    Perfil "spot": w = (escala+3)/6 ∈ [0,1]; patrimonio = caixa + qtd*preço;
    o nocional comprado sai do caixa. Idêntico ao motor herdado.

    Perfil "futuros": w = escala/3 ∈ [-1,+1]; perpétuo TOTALMENTE colateralizado
    (o nocional não consome caixa — o caixa inteiro é o colateral):
      1. liquidação diária: caixa += contratos * (preço[t] - preço[t-1]);
      2. funding do dia sobre a posição carregada: caixa -= contratos * preço[t]
         * funding[t] (long paga funding positivo; SHORT RECEBE — a posição
         contrarian short em euforia é paga para existir). O funding entra
         SEMPRE, inclusive no Grid Search: é P&L intrínseco do instrumento,
         como os 10 bps — não é remuneração de caixa;
      3. recap pré-declarado (fora do grid): se |contratos*preço|/equity >
         RECAP_LIMITE, rebalanceia ao alvo do nível vigente mesmo sem mudança
         de escala (válvula contra deriva de exposição efetiva após perdas).
    Com |w| <= 1, liquidação diária e |r| < 60% (sanity), a equity nunca cruza
    zero em um dia — as métricas herdadas seguem válidas.

    `selic_aa` (opcional, §3): quando informada, o caixa/colateral positivo
    rende a Selic vigente no dia (fator (1+selic_aa[t])^(1/365), coerente com
    N=365), aplicada ANTES de marcar o patrimônio do dia. Entra APENAS na
    simulação final congelada (Módulo 6); o Grid Search roda com caixa a 0%.
    """
    if perfil not in PERFIS:
        raise ValueError(f"perfil desconhecido: {perfil!r} (use um de {PERFIS})")
    ehf = perfil == "futuros"
    if ehf and funding is None:
        raise ValueError("perfil 'futuros' exige a série de funding diário.")

    precos = close.to_numpy(dtype=float)
    sinal_ontem = escala_sinal.shift(1).to_numpy(dtype=float)
    n = len(precos)
    fator_selic = (None if selic_aa is None else
                  (1.0 + selic_aa.to_numpy(dtype=float)) ** (1.0 / N_ANUALIZACAO))
    fund = None if funding is None else funding.to_numpy(dtype=float)

    equity = np.empty(n)
    w_exec = np.empty(n)
    escala_exec = np.empty(n)
    custo_pago = np.zeros(n)
    rebalanceou = np.zeros(n, dtype=bool)
    recap = np.zeros(n, dtype=bool)

    caixa = 1.0
    qtd = 0.0                # spot: qtd_btc >= 0 | futuros: contratos com sinal
    # Estado inicial flat em ambos os perfis: no spot o nível -3 significa
    # 100% caixa; no futuros quem significa "sem posição" é o nível 0.
    escala_atual = 0 if ehf else -3

    for t in range(n):
        if fator_selic is not None and caixa > 0 and not np.isnan(fator_selic[t]):
            caixa *= fator_selic[t]
        if ehf:
            if t > 0:                                  # mark-to-market diário
                caixa += qtd * (precos[t] - precos[t - 1])
            if not np.isnan(fund[t]):                  # carrego de funding
                caixa -= qtd * precos[t] * fund[t]
            patrimonio = caixa                         # posição liquidada no caixa
        else:
            patrimonio = caixa + qtd * precos[t]       # captura r[t] c/ peso antigo
        s = sinal_ontem[t]
        muda_nivel = (not np.isnan(s)) and int(s) != escala_atual
        estourou = (ehf and patrimonio > 0
                    and abs(qtd) * precos[t] / patrimonio > RECAP_LIMITE)
        if muda_nivel or estourou:
            nivel = int(s) if muda_nivel else escala_atual
            w = (nivel / 3.0) if ehf else ((nivel + 3) / 6.0)
            alvo = w * patrimonio
            custo = abs(alvo - qtd * precos[t]) * custo_taxa
            qtd = alvo / precos[t]
            caixa = patrimonio - custo if ehf else patrimonio - alvo - custo
            escala_atual = nivel
            custo_pago[t] = custo
            rebalanceou[t] = muda_nivel
            recap[t] = estourou and not muda_nivel
        equity[t] = caixa if ehf else caixa + qtd * precos[t]
        w_exec[t] = qtd * precos[t] / equity[t]
        escala_exec[t] = escala_atual

    return pd.DataFrame({
        "equity": equity, "w_btc": w_exec, "escala_exec": escala_exec,
        "custo": custo_pago, "rebalanceou": rebalanceou, "recap": recap,
    }, index=close.index)


# ============================================================================
# MÓDULO 4 — MÉTRICAS (N=365, retorno geométrico, guardas de divisão por zero)
# ============================================================================
def calcular_metricas(equity: pd.Series) -> dict:
    """Métricas do §5 sobre uma janela de equity. Denominador 0 => N/A (None)."""
    r = equity.pct_change().dropna().to_numpy()
    T = len(r)
    retorno_total = equity.iloc[-1] / equity.iloc[0] - 1.0
    retorno_anual = (1.0 + retorno_total) ** (N_ANUALIZACAO / T) - 1.0

    std = r.std(ddof=1)
    vol_anual = std * np.sqrt(N_ANUALIZACAO)
    sharpe = (r.mean() / std) * np.sqrt(N_ANUALIZACAO) if std > 0 else None

    downside_anual = np.sqrt(np.sum(np.minimum(r, 0.0) ** 2) / T * N_ANUALIZACAO)
    sortino = retorno_anual / downside_anual if downside_anual > 0 else None

    max_dd = float((equity / equity.cummax() - 1.0).min())
    calmar = retorno_anual / abs(max_dd) if max_dd < 0 else None

    return {
        "retorno_anualizado": float(retorno_anual),
        "volatilidade_anualizada": float(vol_anual),
        "sharpe_rf0": None if sharpe is None else float(sharpe),
        "sortino_mar0": None if sortino is None else float(sortino),
        "calmar": None if calmar is None else float(calmar),
        "max_drawdown": max_dd,
        "retorno_total": float(retorno_total),
        "dias": int(T),
    }


def calcular_beta(equity_estrategia: pd.Series, equity_benchmark: pd.Series) -> float | None:
    """Bônus §5: beta = cov(estratégia, benchmark) / var(benchmark)."""
    r_estr = equity_estrategia.pct_change().dropna()
    r_bench = equity_benchmark.pct_change().dropna().reindex(r_estr.index)
    var = r_bench.var(ddof=1)
    if var == 0 or np.isnan(var):
        return None
    return float(r_estr.cov(r_bench) / var)


def janela_is(serie: pd.Series) -> pd.Series:
    """Janela IS = datas até 31/12/2022 (atribuição pela data do retorno)."""
    return serie[serie.index <= FIM_IN_SAMPLE]


def janela_oos(serie: pd.Series) -> pd.Series:
    """OOS reancorado no último dia IS: 1º retorno da janela é datado de 2023."""
    ultimo_is = serie[serie.index <= FIM_IN_SAMPLE].index[-1]
    return serie[serie.index >= ultimo_is]


# ============================================================================
# MÓDULO 5 — GRID SEARCH IN-SAMPLE (objetivo pré-declarado: Sortino, MAR=0)
# ============================================================================
def grid_search_in_sample(dados: pd.DataFrame, perfil: str) -> tuple[pd.DataFrame, dict]:
    """
    Varre o grid 100% dentro do In-Sample (dados truncados em 31/12/2022 —
    nenhum candle de 2023+ entra no loop). Cada configuração é avaliada com a
    convenção T+1 e custos de 10 bps DENTRO do loop; no perfil futuros o
    funding também fica dentro (P&L do instrumento). Descartes pré-declarados:
    exposição média |w| < 25% ou qualquer métrica N/A. Empate no Sortino é
    resolvido deterministicamente pela ordem de varredura do grid.
    """
    dados_is = dados[dados.index <= FIM_IN_SAMPLE]

    combos_cortes = list(itertools.combinations(GRID_CORTES, 3))  # b1 < b2 < b3
    resultados = []
    melhor = None

    for peso_mayer, peso_fng in GRID_PESOS:
        sinais = calcular_sinais(dados_is, peso_mayer, peso_fng)
        primeiro_z = sinais["score_z"].first_valid_index()
        if primeiro_z is None:
            continue
        close_janela = sinais.loc[primeiro_z:, "close"]
        funding_janela = sinais.loc[primeiro_z:, "funding_d"]
        score_z = sinais["score_z"]

        for b1, b2, b3 in combos_cortes:
            escala = mapear_escala(score_z, b1, b2, b3).loc[primeiro_z:]
            carteira = simular_carteira(close_janela, escala, CUSTO_TAXA, perfil,
                                        funding=funding_janela)

            exposicao_media = float(carteira["w_btc"].mean())
            exposicao_abs = float(carteira["w_btc"].abs().mean())
            met = calcular_metricas(carteira["equity"])
            degenerada = exposicao_abs < EXPOSICAO_MINIMA_IS
            metrica_na = met["sortino_mar0"] is None or met["calmar"] is None

            linha = {
                "peso_mayer": float(peso_mayer), "peso_fng": float(peso_fng),
                "peso_funding": round(1.0 - peso_mayer - peso_fng, 10),
                "b1": b1, "b2": b2, "b3": b3,
                "sortino_is": met["sortino_mar0"], "calmar_is": met["calmar"],
                "sharpe_is": met["sharpe_rf0"], "max_dd_is": met["max_drawdown"],
                "retorno_anual_is": met["retorno_anualizado"],
                "exposicao_media": exposicao_media,
                "exposicao_media_abs": exposicao_abs,
                "n_rebalanceios": int(carteira["rebalanceou"].sum()),
                "n_recaps": int(carteira["recap"].sum()),
                "descartada": bool(degenerada or metrica_na),
                "motivo_descarte": ("exposicao<25%" if degenerada else
                                    "metrica_NA" if metrica_na else ""),
            }
            resultados.append(linha)

            if not linha["descartada"] and (
                    melhor is None or linha["sortino_is"] > melhor["sortino_is"]):
                melhor = linha

    if melhor is None:
        raise RuntimeError(f"Grid Search ({perfil}): nenhuma configuração válida sobreviveu.")
    return pd.DataFrame(resultados), melhor


def vizinhanca_do_otimo(grid: pd.DataFrame, otimo: dict) -> pd.DataFrame:
    """Robustez §6: superfície do objetivo na vizinhança imediata do ótimo."""
    passo_w, passo_b = 0.2, 0.5
    perto = (
        (abs(grid["peso_mayer"] - otimo["peso_mayer"]) <= passo_w + 1e-9)
        & (abs(grid["peso_fng"] - otimo["peso_fng"]) <= passo_w + 1e-9)
        & (abs(grid["b1"] - otimo["b1"]) <= passo_b + 1e-9)
        & (abs(grid["b2"] - otimo["b2"]) <= passo_b + 1e-9)
        & (abs(grid["b3"] - otimo["b3"]) <= passo_b + 1e-9)
    )
    cols = ["peso_mayer", "peso_fng", "peso_funding", "b1", "b2", "b3",
            "sortino_is", "exposicao_media_abs", "n_rebalanceios", "descartada"]
    return grid.loc[perto, cols].sort_values("sortino_is", ascending=False)


# ============================================================================
# MÓDULO 6 — VALIDAÇÃO OUT-OF-SAMPLE (one-shot por perfil, parâmetros congelados)
# ============================================================================
def auditoria_causalidade(dados: pd.DataFrame, peso_mayer: float,
                          peso_fng: float) -> None:
    """
    Prova de que o Z-Score é causal: o Z calculado só com dados até 2022 tem de
    ser idêntico ao Z da série completa nas mesmas datas. Se divergir, alguma
    estatística está vazando informação do futuro — aborta.
    """
    z_full = calcular_sinais(dados, peso_mayer, peso_fng)["score_z"]
    z_is = calcular_sinais(dados[dados.index <= FIM_IN_SAMPLE],
                           peso_mayer, peso_fng)["score_z"]
    comum = z_is.dropna().index
    if not np.allclose(z_full.loc[comum], z_is.loc[comum], equal_nan=True):
        raise AssertionError("AUDITORIA: Z-Score IS difere do full-sample — leakage!")


def executar_backtest_final(dados: pd.DataFrame, params: dict,
                            perfil: str) -> tuple[pd.DataFrame, dict]:
    """
    Roda a série completa UMA única vez com os parâmetros congelados do IS.
    O rolling do Z-Score não é resetado na fronteira (janela causal legítima).
    O benchmark Buy & Hold é BTC SPOT pelo MESMO motor (T+1, custos, mesma data
    de início) via sinal constante +3 no perfil spot — régua única para os dois
    perfis, e é o ativo que qualquer participante poderia simplesmente comprar.
    """
    sinais = calcular_sinais(dados, params["peso_mayer"], params["peso_fng"])
    primeiro_z = sinais["score_z"].first_valid_index()
    escala = mapear_escala(sinais["score_z"], params["b1"], params["b2"], params["b3"])

    close = sinais.loc[primeiro_z:, "close"]
    escala_j = escala.loc[primeiro_z:]
    selic_j = sinais.loc[primeiro_z:, "selic_aa"]
    funding_j = sinais.loc[primeiro_z:, "funding_d"]
    sinal_bh = pd.Series(float(ESCALA_BUY_HOLD), index=close.index)

    # Remuneração do caixa/colateral pela Selic entra SÓ nesta simulação final,
    # já com os parâmetros congelados pelo Grid Search — que roda com caixa a 0%
    # (Módulo 5). O funding do perfil futuros NÃO é opcional nem "de reporte":
    # esteve dentro do grid e está aqui — é P&L do instrumento. A versão "bruta"
    # zera apenas o custo de transação (10 bps), nunca o funding.
    fund_kw = funding_j if perfil == "futuros" else None
    estrategia = simular_carteira(close, escala_j, CUSTO_TAXA, perfil, selic_j, fund_kw)
    estrategia_bruta = simular_carteira(close, escala_j, 0.0, perfil, selic_j, fund_kw)
    buy_hold = simular_carteira(close, sinal_bh, CUSTO_TAXA, "spot", selic_j)
    buy_hold_bruto = simular_carteira(close, sinal_bh, 0.0, "spot", selic_j)

    serie = sinais.loc[primeiro_z:].copy()
    serie["escala_sinal"] = escala_j
    serie["escala_exec"] = estrategia["escala_exec"]
    serie["w_btc"] = estrategia["w_btc"]
    serie["rebalanceou"] = estrategia["rebalanceou"]
    serie["recap"] = estrategia["recap"]
    serie["custo"] = estrategia["custo"]
    serie["equity_liq"] = estrategia["equity"]
    serie["equity_bruta"] = estrategia_bruta["equity"]
    serie["equity_bh_liq"] = buy_hold["equity"]
    serie["equity_bh_bruta"] = buy_hold_bruto["equity"]

    metricas = {}
    for periodo, janela in (("in_sample", janela_is), ("out_of_sample", janela_oos)):
        eq_estr, eq_bh = janela(estrategia["equity"]), janela(buy_hold["equity"])
        metricas[periodo] = {
            "estrategia_liquida": calcular_metricas(eq_estr),
            "estrategia_bruta": calcular_metricas(janela(estrategia_bruta["equity"])),
            "buy_hold_liquido": calcular_metricas(eq_bh),
            "buy_hold_bruto": calcular_metricas(janela(buy_hold_bruto["equity"])),
            "beta_vs_buy_hold": calcular_beta(eq_estr, eq_bh),
            "exposicao_media_btc": float(janela(estrategia["w_btc"]).mean()),
            "exposicao_media_abs": float(janela(estrategia["w_btc"]).abs().mean()),
            "n_rebalanceios": int(janela(estrategia["rebalanceou"]).sum()),
            "n_recaps": int(janela(estrategia["recap"]).sum()),
            "inicio": str(eq_estr.index[0].date()),
            "fim": str(eq_estr.index[-1].date()),
        }
    return serie, metricas


# ============================================================================
# RELATÓRIO
# ============================================================================
def _fmt(v, pct=False) -> str:
    if v is None:
        return "N/A"
    return f"{v:+.2%}" if pct else f"{v:+.3f}"


def imprimir_relatorio(perfil: str, otimo: dict, vizinhos: pd.DataFrame,
                       metricas: dict) -> None:
    rotulo_perfil = "SPOT (BTC à vista / caixa)" if perfil == "spot" else \
                    "FUTUROS L/S (perpétuo colateralizado, |w| <= 1)"
    print("\n" + "=" * 74)
    print(f"PERFIL {rotulo_perfil}")
    print("PARÂMETROS CONGELADOS (Grid Search In-Sample | objetivo: Sortino MAR=0)")
    print("=" * 74)
    print(f"  Peso_Mayer = {otimo['peso_mayer']:.1f}  |  Peso_FNG = {otimo['peso_fng']:.1f}"
          f"  |  Peso_Funding = {otimo['peso_funding']:.1f}")
    print(f"  Cortes: b1 = {otimo['b1']:.2f}  b2 = {otimo['b2']:.2f}  b3 = {otimo['b3']:.2f}")
    print(f"  Sortino IS = {_fmt(otimo['sortino_is'])}  |  Exposição média |w| IS = "
          f"{otimo['exposicao_media_abs']:.1%}  |  Rebalanceios IS = {otimo['n_rebalanceios']}")

    print("\n  Vizinhança do ótimo (robustez — superfície plana = parâmetros robustos):")
    print(vizinhos.to_string(index=False))

    for periodo, rotulo in (("in_sample", "IN-SAMPLE (treino, até 31/12/2022)"),
                            ("out_of_sample", "OUT-OF-SAMPLE (one-shot, 2023+)")):
        m = metricas[periodo]
        print("\n" + "=" * 74)
        print(f"{rotulo}  [{m['inicio']} -> {m['fim']}]")
        print("=" * 74)
        print(f"{'Métrica':<26}{'Estratégia (líq.)':>18}{'Estratégia (bruta)':>20}{'B&H spot (líq.)':>18}")
        linhas = [
            ("Retorno anualizado", "retorno_anualizado", True),
            ("Volatilidade anual.", "volatilidade_anualizada", True),
            ("Sharpe (rf=0)", "sharpe_rf0", False),
            ("Sortino (MAR=0)", "sortino_mar0", False),
            ("Calmar", "calmar", False),
            ("Max Drawdown", "max_drawdown", True),
        ]
        for rotulo_m, chave, pct in linhas:
            print(f"{rotulo_m:<26}"
                  f"{_fmt(m['estrategia_liquida'][chave], pct):>18}"
                  f"{_fmt(m['estrategia_bruta'][chave], pct):>20}"
                  f"{_fmt(m['buy_hold_liquido'][chave], pct):>18}")
        print(f"{'Beta vs. B&H spot':<26}{_fmt(m['beta_vs_buy_hold']):>18}")
        print(f"{'Exposição média (c/ sinal)':<26}{m['exposicao_media_btc']:>+17.1%}"
              f"{'':>2}{'|w| média:':>18} {m['exposicao_media_abs']:.1%}")
        print(f"{'Rebalanceios':<26}{m['n_rebalanceios']:>18}"
              + (f"{'Recaps:':>20} {m['n_recaps']}" if perfil == "futuros" else ""))

    print("\nCaveat (PRE_REGISTRO §7): 2018-2022 contém ~1,5 ciclo de BTC — poucas")
    print("observações independentes; robustez defendida pela vizinhança do ótimo.")


# ============================================================================
# ORQUESTRAÇÃO
# ============================================================================
def main() -> None:
    import sys

    atualizar = "--atualizar" in sys.argv
    os.makedirs(DIR_RESULTADOS, exist_ok=True)

    print("[1/4] Dados: cache point-in-time + sanity check..."
          + (" (atualizando cauda do cache)" if atualizar else ""))
    dados = carregar_dados(atualizar)
    print(f"      {len(dados)} dias | {dados.index[0].date()} -> {dados.index[-1].date()}")

    for perfil in PERFIS:
        print(f"\n[2/4] Grid Search In-Sample — perfil {perfil} (T+1 + custos no loop)...")
        grid, otimo = grid_search_in_sample(dados, perfil)
        n_validas = int((~grid["descartada"]).sum())
        print(f"      {len(grid)} combinações | {n_validas} válidas | "
              f"{len(grid) - n_validas} descartadas (degeneradas/N-A)")

        print(f"[3/4] Auditoria de causalidade do Z-Score na fronteira IS/OOS...")
        auditoria_causalidade(dados, otimo["peso_mayer"], otimo["peso_fng"])
        print("      OK — Z-Score IS idêntico ao da série completa (sem leakage).")

        print(f"[4/4] Validação Out-of-Sample one-shot — perfil {perfil}...")
        serie, metricas = executar_backtest_final(dados, otimo, perfil)

        grid.to_csv(os.path.join(DIR_RESULTADOS, f"grid_search_is_{perfil}.csv"),
                    index=False)
        serie.to_csv(os.path.join(DIR_RESULTADOS, f"serie_backtest_{perfil}.csv"))
        with open(os.path.join(DIR_RESULTADOS,
                               f"parametros_otimos_{perfil}.json"), "w") as f:
            json.dump({k: otimo[k] for k in
                       ("peso_mayer", "peso_fng", "peso_funding", "b1", "b2", "b3",
                        "sortino_is", "exposicao_media", "exposicao_media_abs",
                        "n_rebalanceios", "n_recaps")}, f, indent=2)
        with open(os.path.join(DIR_RESULTADOS, f"metricas_{perfil}.json"), "w") as f:
            json.dump(metricas, f, indent=2, ensure_ascii=False)

        imprimir_relatorio(perfil, otimo, vizinhanca_do_otimo(grid, otimo), metricas)

    print(f"\nSaídas gravadas em '{DIR_RESULTADOS}/' (série, grid, parâmetros, métricas"
          " — sufixadas por perfil).")


if __name__ == "__main__":
    main()
