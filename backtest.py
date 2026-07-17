# -*- coding: utf-8 -*-
"""
MOTOR QUANTITATIVO — Desafio Quant AI 2026 (Itaú Asset)
========================================================
Estratégia contrarian de alocação dinâmica BTC/Caixa em 7 níveis, dirigida pelo
Z-Score móvel (90d) do Score Combinado (Múltiplo de Mayer + Fear & Greed Index).

Regras de blindagem implementadas (CLAUDE.md §2–§6):
  - Dados point-in-time: cache local dos CSVs brutos; forward-fill apenas no FNG.
  - Sanity check dos dados brutos ANTES de qualquer métrica (aborta em violação).
  - Convenção T+1 única: retorno_estrategia[t] = w_sinal[t-2] * r[t]
    (sinal no close de D -> execução no close de D+1 -> captura a partir de D+2);
    custo de 10 bps debitado no dia da execução. Mesma convenção para o benchmark.
  - Warm-up: janela avaliada começa no primeiro dia com Z-Score válido (~mai/2018);
    antes disso nenhum dia conta — nem para a estratégia, nem para o Buy & Hold.
  - Z-Score estritamente causal: .rolling(90, min_periods=90); std < 1e-8 mantém
    a escala anterior (nunca divide por ~zero).
  - Rebalanceamento somente na mudança de nível da escala; equity marcada a
    mercado (caixa + qtd_BTC * preço), reportada com e sem custos.
  - Grid Search só no In-Sample (retornos até 31/12/2022); objetivo único
    pré-declarado = Sortino (MAR=0) com T+1 e custos dentro do loop; restrição
    de exposição média >= 25%; métricas N/A descartam a configuração.
  - Out-of-Sample one-shot com parâmetros congelados; rolling NÃO é resetado
    na fronteira de jan/2023 (janela causal olhando para trás não é leakage).
  - Anualização única N=365 (BTC negocia 24/7); retorno anualizado geométrico.

Saídas (consumidas pela Fase 4 / Plotly):
  dados/btc_usd_raw.csv, dados/fng_raw.csv          (cache point-in-time)
  resultados/serie_backtest.csv                     (série diária consolidada)
  resultados/grid_search_is.csv                     (superfície p/ heatmap)
  resultados/parametros_otimos.json                 (parâmetros congelados)
  resultados/metricas.json                          (métricas IS/OOS)
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

DATA_INICIO_PRECO = "2017-01-01"   # warm-up da SMA 200 (FNG só existe de 2018-02-01)
FIM_IN_SAMPLE = pd.Timestamp("2022-12-31")   # IS/OOS atribuído pela data do retorno
JANELA_SMA = 200
JANELA_Z = 90
GUARDA_STD = 1e-8                  # std móvel abaixo disso -> mantém escala anterior
CUSTO_TAXA = 0.001                 # 10 bps sobre o valor negociado, no dia da execução
N_ANUALIZACAO = 365                # BTC negocia 24/7 — nunca 252/238
LIMITE_RETORNO_DIARIO = 0.60       # sanity check: |r| >= 60% aborta

# Grid grosso e determinístico (§6): 4 parâmetros, poucas centenas de combinações.
GRID_PESO_MAYER = np.round(np.arange(0.0, 1.0001, 0.1), 2)          # passo 0,1
GRID_CORTES = np.round(np.arange(0.25, 2.0001, 0.25), 2)            # passo 0,25σ
EXPOSICAO_MINIMA_IS = 0.25         # restrição anti-solução-degenerada

ESCALA_BUY_HOLD = 3                # +3 => w_BTC = 100% (benchmark passa pelo mesmo motor)


# ============================================================================
# MÓDULO 1 — DADOS E CACHE (point-in-time, anti-leakage)
# ============================================================================
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
    df.to_csv(CACHE_BTC)


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
    df.to_csv(CACHE_FNG)


def sanity_check(close: pd.Series, fng: pd.Series) -> None:
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


def carregar_dados() -> pd.DataFrame:
    """Garante o cache, valida os brutos e devolve o painel diário alinhado."""
    os.makedirs(DIR_DADOS, exist_ok=True)
    if not os.path.exists(CACHE_BTC):
        baixar_btc()
    if not os.path.exists(CACHE_FNG):
        baixar_fng()

    btc = pd.read_csv(CACHE_BTC, index_col="Date", parse_dates=True)
    fng = pd.read_csv(CACHE_FNG, index_col="Date", parse_dates=True)

    dados = pd.DataFrame({"close": btc["Close"]})
    # Reindexação no calendário do preço + forward-fill APENAS (bfill/interpolação
    # usariam informação do futuro — look-ahead). Antes de 2018-02-01 o FNG fica NaN.
    dados["fng"] = fng["fng"].reindex(dados.index).ffill()

    sanity_check(dados["close"], fng["fng"])
    return dados


# ============================================================================
# MÓDULO 2 — SINAIS: Mayer, FNG normalizado, Score, Z-Score causal, escala
# ============================================================================
def calcular_sinais(dados: pd.DataFrame, peso_mayer: float) -> pd.DataFrame:
    """Score Combinado e Z-Score móvel de 90 dias, ambos estritamente causais."""
    df = dados.copy()
    df["sma200"] = df["close"].rolling(JANELA_SMA, min_periods=JANELA_SMA).mean()
    df["mayer"] = df["close"] / df["sma200"]
    df["fng_norm"] = df["fng"] / 50.0

    # NaN propaga: mesmo com peso 0 em um indicador, o Score só nasce quando os
    # DOIS existem (2018-02-01) — janela de avaliação idêntica p/ todo o grid.
    df["score"] = peso_mayer * df["mayer"] + (1.0 - peso_mayer) * df["fng_norm"]

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
# MÓDULO 3 — MOTOR DE CARTEIRA (T+1, custos, equity marcada a mercado)
# ============================================================================
def simular_carteira(close: pd.Series, escala_sinal: pd.Series,
                     custo_taxa: float) -> pd.DataFrame:
    """
    Simula a carteira na janela avaliada (1º índice = primeiro dia com sinal
    válido). Convenção T+1 do §4: o sinal do fechamento de D é executado no
    fechamento de D+1 (custo debitado nesse dia) e o peso novo captura retornos
    a partir de D+2 — equivalente a retorno[t] = w_sinal[t-2] * r[t].

    Loop explícito (e não encadeamento de percentuais) porque a equity é
    marcada a mercado: patrimonio = caixa + qtd_BTC * preço, recalculado a cada
    rebalanceamento (§4). Rebalanceia SOMENTE quando a escala muda de nível.
    """
    precos = close.to_numpy(dtype=float)
    sinal_ontem = escala_sinal.shift(1).to_numpy(dtype=float)
    n = len(precos)

    equity = np.empty(n)
    w_exec = np.empty(n)
    escala_exec = np.empty(n)
    custo_pago = np.zeros(n)
    rebalanceou = np.zeros(n, dtype=bool)

    caixa, qtd_btc = 1.0, 0.0
    escala_atual = -3                      # estado inicial: 100% caixa (w_BTC = 0)

    for t in range(n):
        patrimonio = caixa + qtd_btc * precos[t]   # captura r[t] com o peso antigo
        s = sinal_ontem[t]
        if not np.isnan(s) and int(s) != escala_atual:
            alvo_btc = ((int(s) + 3) / 6.0) * patrimonio
            custo = abs(alvo_btc - qtd_btc * precos[t]) * custo_taxa
            qtd_btc = alvo_btc / precos[t]
            caixa = patrimonio - alvo_btc - custo
            escala_atual = int(s)
            custo_pago[t] = custo
            rebalanceou[t] = True
        equity[t] = caixa + qtd_btc * precos[t]
        w_exec[t] = qtd_btc * precos[t] / equity[t]
        escala_exec[t] = escala_atual

    return pd.DataFrame({
        "equity": equity, "w_btc": w_exec, "escala_exec": escala_exec,
        "custo": custo_pago, "rebalanceou": rebalanceou,
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
def grid_search_in_sample(dados: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Varre o grid 100% dentro do In-Sample (dados truncados em 31/12/2022 —
    nenhum candle de 2023+ entra no loop). Cada configuração é avaliada com a
    convenção T+1 e custos de 10 bps DENTRO do loop. Descartes pré-declarados:
    exposição média a BTC < 25% ou qualquer métrica N/A. Empate no Sortino é
    resolvido deterministicamente pela ordem de varredura do grid.
    """
    dados_is = dados[dados.index <= FIM_IN_SAMPLE]

    combos_cortes = list(itertools.combinations(GRID_CORTES, 3))  # b1 < b2 < b3
    resultados = []
    melhor = None

    for peso_mayer in GRID_PESO_MAYER:
        sinais = calcular_sinais(dados_is, peso_mayer)
        primeiro_z = sinais["score_z"].first_valid_index()
        if primeiro_z is None:
            continue
        close_janela = sinais.loc[primeiro_z:, "close"]
        score_z = sinais["score_z"]

        for b1, b2, b3 in combos_cortes:
            escala = mapear_escala(score_z, b1, b2, b3).loc[primeiro_z:]
            carteira = simular_carteira(close_janela, escala, CUSTO_TAXA)

            exposicao_media = float(carteira["w_btc"].mean())
            met = calcular_metricas(carteira["equity"])
            degenerada = exposicao_media < EXPOSICAO_MINIMA_IS
            metrica_na = met["sortino_mar0"] is None or met["calmar"] is None

            linha = {
                "peso_mayer": float(peso_mayer), "b1": b1, "b2": b2, "b3": b3,
                "sortino_is": met["sortino_mar0"], "calmar_is": met["calmar"],
                "sharpe_is": met["sharpe_rf0"], "max_dd_is": met["max_drawdown"],
                "retorno_anual_is": met["retorno_anualizado"],
                "exposicao_media": exposicao_media,
                "n_rebalanceios": int(carteira["rebalanceou"].sum()),
                "descartada": bool(degenerada or metrica_na),
                "motivo_descarte": ("exposicao<25%" if degenerada else
                                    "metrica_NA" if metrica_na else ""),
            }
            resultados.append(linha)

            if not linha["descartada"] and (
                    melhor is None or linha["sortino_is"] > melhor["sortino_is"]):
                melhor = linha

    if melhor is None:
        raise RuntimeError("Grid Search: nenhuma configuração válida sobreviveu.")
    return pd.DataFrame(resultados), melhor


def vizinhanca_do_otimo(grid: pd.DataFrame, otimo: dict) -> pd.DataFrame:
    """Robustez §6: superfície do objetivo na vizinhança imediata do ótimo."""
    passo_w, passo_b = 0.1, 0.25
    perto = (
        (abs(grid["peso_mayer"] - otimo["peso_mayer"]) <= passo_w + 1e-9)
        & (abs(grid["b1"] - otimo["b1"]) <= passo_b + 1e-9)
        & (abs(grid["b2"] - otimo["b2"]) <= passo_b + 1e-9)
        & (abs(grid["b3"] - otimo["b3"]) <= passo_b + 1e-9)
    )
    cols = ["peso_mayer", "b1", "b2", "b3", "sortino_is", "exposicao_media",
            "n_rebalanceios", "descartada"]
    return grid.loc[perto, cols].sort_values("sortino_is", ascending=False)


# ============================================================================
# MÓDULO 6 — VALIDAÇÃO OUT-OF-SAMPLE (one-shot, parâmetros congelados)
# ============================================================================
def auditoria_causalidade(dados: pd.DataFrame, peso_mayer: float) -> None:
    """
    Prova de que o Z-Score é causal: o Z calculado só com dados até 2022 tem de
    ser idêntico ao Z da série completa nas mesmas datas. Se divergir, alguma
    estatística está vazando informação do futuro — aborta.
    """
    z_full = calcular_sinais(dados, peso_mayer)["score_z"]
    z_is = calcular_sinais(dados[dados.index <= FIM_IN_SAMPLE], peso_mayer)["score_z"]
    comum = z_is.dropna().index
    if not np.allclose(z_full.loc[comum], z_is.loc[comum], equal_nan=True):
        raise AssertionError("AUDITORIA: Z-Score IS difere do full-sample — leakage!")


def executar_backtest_final(dados: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, dict]:
    """
    Roda a série completa UMA única vez com os parâmetros congelados do IS.
    O rolling do Z-Score não é resetado na fronteira (janela causal legítima).
    O benchmark Buy & Hold passa pelo MESMO motor (T+1, custos, mesma data de
    início) via sinal constante +3.
    """
    sinais = calcular_sinais(dados, params["peso_mayer"])
    primeiro_z = sinais["score_z"].first_valid_index()
    escala = mapear_escala(sinais["score_z"], params["b1"], params["b2"], params["b3"])

    close = sinais.loc[primeiro_z:, "close"]
    escala_j = escala.loc[primeiro_z:]
    sinal_bh = pd.Series(float(ESCALA_BUY_HOLD), index=close.index)

    estrategia = simular_carteira(close, escala_j, CUSTO_TAXA)
    estrategia_bruta = simular_carteira(close, escala_j, 0.0)
    buy_hold = simular_carteira(close, sinal_bh, CUSTO_TAXA)
    buy_hold_bruto = simular_carteira(close, sinal_bh, 0.0)

    serie = sinais.loc[primeiro_z:].copy()
    serie["escala_sinal"] = escala_j
    serie["escala_exec"] = estrategia["escala_exec"]
    serie["w_btc"] = estrategia["w_btc"]
    serie["rebalanceou"] = estrategia["rebalanceou"]
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
            "n_rebalanceios": int(janela(estrategia["rebalanceou"]).sum()),
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


def imprimir_relatorio(otimo: dict, vizinhos: pd.DataFrame, metricas: dict) -> None:
    print("\n" + "=" * 74)
    print("PARÂMETROS CONGELADOS (Grid Search In-Sample | objetivo: Sortino MAR=0)")
    print("=" * 74)
    print(f"  Peso_Mayer = {otimo['peso_mayer']:.1f}  |  Peso_FNG = {1 - otimo['peso_mayer']:.1f}")
    print(f"  Cortes: b1 = {otimo['b1']:.2f}  b2 = {otimo['b2']:.2f}  b3 = {otimo['b3']:.2f}")
    print(f"  Sortino IS = {_fmt(otimo['sortino_is'])}  |  Exposição média IS = "
          f"{otimo['exposicao_media']:.1%}  |  Rebalanceios IS = {otimo['n_rebalanceios']}")

    print("\n  Vizinhança do ótimo (robustez — superfície plana = parâmetros robustos):")
    print(vizinhos.to_string(index=False))

    for periodo, rotulo in (("in_sample", "IN-SAMPLE (treino, até 31/12/2022)"),
                            ("out_of_sample", "OUT-OF-SAMPLE (one-shot, 2023+)")):
        m = metricas[periodo]
        print("\n" + "=" * 74)
        print(f"{rotulo}  [{m['inicio']} -> {m['fim']}]")
        print("=" * 74)
        print(f"{'Métrica':<26}{'Estratégia (líq.)':>18}{'Estratégia (bruta)':>20}{'Buy&Hold (líq.)':>18}")
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
        print(f"{'Beta vs. Buy & Hold':<26}{_fmt(m['beta_vs_buy_hold']):>18}")
        print(f"{'Exposição média BTC':<26}{m['exposicao_media_btc']:>17.1%}"
              f"{'':>20}{'100.0%':>18}")
        print(f"{'Rebalanceios':<26}{m['n_rebalanceios']:>18}")

    print("\nCaveat (§6): 2018-2022 contém ~1,5 ciclo de BTC — poucas observações")
    print("independentes; a robustez é defendida pela vizinhança plana do ótimo.")


# ============================================================================
# ORQUESTRAÇÃO
# ============================================================================
def main() -> None:
    os.makedirs(DIR_RESULTADOS, exist_ok=True)

    print("[1/4] Dados: cache point-in-time + sanity check...")
    dados = carregar_dados()
    print(f"      {len(dados)} dias | {dados.index[0].date()} -> {dados.index[-1].date()}")

    print("[2/4] Grid Search In-Sample (T+1 + custos dentro do loop)...")
    grid, otimo = grid_search_in_sample(dados)
    n_validas = int((~grid["descartada"]).sum())
    print(f"      {len(grid)} combinações | {n_validas} válidas | "
          f"{len(grid) - n_validas} descartadas (degeneradas/N-A)")

    print("[3/4] Auditoria de causalidade do Z-Score na fronteira IS/OOS...")
    auditoria_causalidade(dados, otimo["peso_mayer"])
    print("      OK — Z-Score IS idêntico ao da série completa (sem leakage).")

    print("[4/4] Validação Out-of-Sample one-shot (parâmetros congelados)...")
    serie, metricas = executar_backtest_final(dados, otimo)

    grid.to_csv(os.path.join(DIR_RESULTADOS, "grid_search_is.csv"), index=False)
    serie.to_csv(os.path.join(DIR_RESULTADOS, "serie_backtest.csv"))
    with open(os.path.join(DIR_RESULTADOS, "parametros_otimos.json"), "w") as f:
        json.dump({k: otimo[k] for k in ("peso_mayer", "b1", "b2", "b3", "sortino_is",
                                         "exposicao_media", "n_rebalanceios")}, f, indent=2)
    with open(os.path.join(DIR_RESULTADOS, "metricas.json"), "w") as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)

    imprimir_relatorio(otimo, vizinhanca_do_otimo(grid, otimo), metricas)
    print(f"\nSaídas gravadas em '{DIR_RESULTADOS}/' (série, grid, parâmetros, métricas).")


if __name__ == "__main__":
    main()
