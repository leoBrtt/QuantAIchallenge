# -*- coding: utf-8 -*-
"""
ANÁLISE PÓS-OOS — Desafio Quant AI 2026 (Itaú Asset)
=====================================================
Análises complementares para o relatório (critério 4.5 do Manual de Avaliação),
calculadas EXCLUSIVAMENTE a partir das saídas congeladas do motor
(`resultados/serie_backtest.csv`) e do próprio motor (`backtest.py`) reutilizado
sem nenhuma modificação. Nenhum parâmetro é reotimizado aqui — todas as regras
comparativas abaixo foram fixadas a priori e estão declaradas no relatório como
análise pós-OOS (não é re-tuning: o sinal congelado nunca é alterado).

Conteúdo:
  1. Retornos ano a ano (estratégia líquida vs. Buy & Hold líquido).
  2. Janelas de crise (COVID mar/2020, FTX nov/2022, correção 2026) — drawdown
     pico-a-vale dentro de janelas de calendário declaradas abaixo.
  3. Information Ratio canônico (retornos ativos vs. Buy & Hold), IS e OOS.
  4. Distribuição de tempo por nível da escala + diagnóstico de whipsaw.
  5. Payoff dos extremos: retorno forward do BTC (30/90/180d) após entradas
     em −3 (venda por euforia) e +3 (compra por pânico).
  6. Benchmark estático 50/50: o MESMO motor com sinal constante 0 (compra 50%
     no primeiro dia e deixa derivar — regra fixada a priori), com a MESMA
     remuneração de caixa pela Selic da estratégia oficial (comparação justa),
     p/ separar quanto do resultado vem da exposição média e quanto vem do
     timing.
  7. Sensibilidade pós-fato: custo (10/25/50 bps) × política de caixa (0% —
     convenção anterior à mudança de regra — vs. Selic real point-in-time),
     com o sinal congelado — estudo de robustez, não re-tuning.

Saídas:
  resultados/analise_resultados.json   (todos os números consumidos no relatório)
  stdout                               (relatório legível)
"""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from backtest import (CUSTO_TAXA, N_ANUALIZACAO, PERFIS, calcular_beta,
                      calcular_metricas, janela_is, janela_oos,
                      simular_carteira)

DIR_RESULTADOS = "resultados"


def _arq_serie(perfil: str) -> str:
    return os.path.join(DIR_RESULTADOS, f"serie_backtest_{perfil}.csv")


def _arq_saida(perfil: str) -> str:
    return os.path.join(DIR_RESULTADOS, f"analise_resultados_{perfil}.json")

# Janelas de crise declaradas a priori (datas de calendário, não escolhidas
# a posteriori para favorecer a estratégia): pico pré-crash -> vale conhecido.
JANELAS_CRISE = {
    "covid_2020": ("2020-02-01", "2020-04-30"),
    "ftx_2022": ("2022-10-31", "2022-11-30"),
    "correcao_2026": ("2026-01-01", None),  # None = até o fim da série
}

HORIZONTES_FWD = (30, 90, 180)             # dias corridos p/ payoff dos extremos
GRID_CUSTOS_BPS = (10, 25, 50)             # sensibilidade de custo


def carregar_serie(perfil: str) -> pd.DataFrame:
    serie = pd.read_csv(_arq_serie(perfil), index_col="Date", parse_dates=True)
    obrigatorias = {"close", "escala_sinal", "escala_exec", "rebalanceou",
                    "equity_liq", "equity_bh_liq", "selic_aa", "funding_d"}
    faltando = obrigatorias - set(serie.columns)
    if faltando:
        raise ValueError(f"{_arq_serie(perfil)} sem colunas {faltando} — rodar backtest.py antes.")
    return serie


# ----------------------------------------------------------------------------
# 1. Ano a ano
# ----------------------------------------------------------------------------
def retornos_anuais(serie: pd.DataFrame) -> dict:
    """Retorno de cada ano civil = equity no último dia do ano / equity no
    último dia do ano anterior − 1 (2018 parte do primeiro dia da janela)."""
    resultado = {}
    for ano, grupo in serie.groupby(serie.index.year):
        fim = grupo.index[-1]
        anteriores = serie.index[serie.index < grupo.index[0]]
        base = anteriores[-1] if len(anteriores) else grupo.index[0]
        resultado[int(ano)] = {
            "estrategia_liq": float(serie.at[fim, "equity_liq"] / serie.at[base, "equity_liq"] - 1),
            "buy_hold_liq": float(serie.at[fim, "equity_bh_liq"] / serie.at[base, "equity_bh_liq"] - 1),
            "de": str(base.date()), "ate": str(fim.date()),
        }
    return resultado


# ----------------------------------------------------------------------------
# 2. Janelas de crise (drawdown pico-a-vale dentro da janela declarada)
# ----------------------------------------------------------------------------
def _drawdown_janela(equity: pd.Series, ini: str, fim: str | None) -> float:
    recorte = equity.loc[ini:] if fim is None else equity.loc[ini:fim]
    return float((recorte / recorte.cummax() - 1.0).min())


def janelas_de_crise(serie: pd.DataFrame) -> dict:
    resultado = {}
    for nome, (ini, fim) in JANELAS_CRISE.items():
        resultado[nome] = {
            "janela": f"{ini} -> {fim or str(serie.index[-1].date())}",
            "dd_estrategia": _drawdown_janela(serie["equity_liq"], ini, fim),
            "dd_buy_hold": _drawdown_janela(serie["equity_bh_liq"], ini, fim),
        }
    return resultado


# ----------------------------------------------------------------------------
# 3. Information Ratio canônico (retornos ativos vs. Buy & Hold)
# ----------------------------------------------------------------------------
def information_ratio(serie: pd.DataFrame) -> dict:
    """IR canônico do §5 do CLAUDE.md: média/desvio dos retornos ATIVOS diários
    (estratégia − benchmark), anualizado por √365. Reporta também o tracking
    error e a diferença de retorno anualizado geométrico, para leitura completa."""
    resultado = {}
    r_estr = serie["equity_liq"].pct_change().dropna()
    r_bh = serie["equity_bh_liq"].pct_change().dropna()
    ativo = (r_estr - r_bh).dropna()
    for periodo, janela in (("in_sample", janela_is), ("out_of_sample", janela_oos)):
        a = janela(ativo)
        if periodo == "out_of_sample":       # janela_oos reancora no último dia IS
            a = a.iloc[1:]                   # o 1º elemento é o retorno de 31/12
        te = a.std(ddof=1) * np.sqrt(N_ANUALIZACAO)
        ir = a.mean() / a.std(ddof=1) * np.sqrt(N_ANUALIZACAO)
        m_estr = calcular_metricas(janela(serie["equity_liq"]))
        m_bh = calcular_metricas(janela(serie["equity_bh_liq"]))
        resultado[periodo] = {
            "ir_canonico": float(ir),
            "tracking_error_anual": float(te),
            "retorno_ativo_geometrico_aa": float(
                m_estr["retorno_anualizado"] - m_bh["retorno_anualizado"]),
            "dias": int(len(a)),
        }
    return resultado


# ----------------------------------------------------------------------------
# 4. Tempo por nível + whipsaw
# ----------------------------------------------------------------------------
def distribuicao_e_whipsaw(serie: pd.DataFrame) -> dict:
    dist = (serie["escala_exec"].value_counts(normalize=True)
            .sort_index().round(6))
    saltos = serie["escala_exec"].diff().abs()
    rebal = serie["rebalanceou"].astype(bool)
    n_rebal = int(rebal.sum())
    n_saltos_2mais = int((saltos[rebal] >= 2).sum())
    anos = (serie.index[-1] - serie.index[0]).days / 365.25
    return {
        "pct_tempo_por_nivel": {str(int(k)): float(v) for k, v in dist.items()},
        "n_rebalanceios": n_rebal,
        "rebalanceios_por_ano": float(n_rebal / anos),
        "saltos_2niveis_ou_mais": n_saltos_2mais,
        "pct_saltos_2niveis": float(n_saltos_2mais / n_rebal) if n_rebal else None,
    }


# ----------------------------------------------------------------------------
# 5. Payoff dos extremos (autópsia do sinal)
# ----------------------------------------------------------------------------
def payoff_extremos(serie: pd.DataFrame) -> dict:
    """Retorno forward do BTC após cada ENTRADA nos níveis extremos da escala
    executada (dia em que o nível passa a ser −3 ou +3). Mede se 'vender na
    euforia' e 'comprar no pânico' anteciparam corretamente o preço."""
    close = serie["close"]
    exec_ = serie["escala_exec"]
    resultado = {}
    for nivel, rotulo in ((-3, "entradas_em_-3_euforia"), (3, "entradas_em_+3_panico")):
        entradas = serie.index[(exec_ == nivel) & (exec_.shift(1) != nivel)]
        info = {"n_entradas": int(len(entradas))}
        for h in HORIZONTES_FWD:
            fwd = (close.shift(-h) / close - 1.0).loc[entradas].dropna()
            info[f"fwd_{h}d"] = {
                "n": int(len(fwd)),
                "media": float(fwd.mean()) if len(fwd) else None,
                "mediana": float(fwd.median()) if len(fwd) else None,
                "pct_positivo": float((fwd > 0).mean()) if len(fwd) else None,
            }
        resultado[rotulo] = info
    return resultado


# ----------------------------------------------------------------------------
# 6. Benchmark estático 50/50 (mesmo motor, sinal constante 0)
# ----------------------------------------------------------------------------
def benchmark_estatico(serie: pd.DataFrame) -> dict:
    """Regra fixada a priori: sinal constante 0 (=> 50% BTC no primeiro dia
    executável) no MESMO motor — mesma convenção T+1, mesmo custo, mesma data
    de início e a MESMA remuneração de caixa pela Selic da estratégia oficial
    (senão a comparação misturaria efeito de timing com efeito de política de
    caixa). Como a escala nunca muda, a carteira compra uma vez e deriva.
    Separa a contribuição da exposição média (dosagem) da do timing (sinal).
    O 50/50 é sempre SPOT (no perfil futuros a escala 0 significa flat, o que
    não serve de régua de dosagem — a régua comum aos dois perfis é o spot)."""
    close = serie["close"]
    sinal_zero = pd.Series(0.0, index=close.index)
    carteira = simular_carteira(close, sinal_zero, CUSTO_TAXA, "spot",
                                serie["selic_aa"])
    resultado = {}
    for periodo, janela in (("in_sample", janela_is), ("out_of_sample", janela_oos)):
        eq = janela(carteira["equity"])
        met = calcular_metricas(eq)
        met["beta_vs_buy_hold"] = calcular_beta(eq, janela(serie["equity_bh_liq"]))
        met["exposicao_media_btc"] = float(janela(carteira["w_btc"]).mean())
        resultado[periodo] = met
    return resultado


# ----------------------------------------------------------------------------
# 7. Sensibilidade custo × política de caixa (sinal congelado — não re-tuning)
# ----------------------------------------------------------------------------
def sensibilidade_custo_caixa(serie: pd.DataFrame, perfil: str) -> dict:
    """Reusa backtest.simular_carteira (motor oficial, sem reimplementação) sob
    custos mais severos (25/50 bps) e comparando as duas políticas de caixa: a
    convenção do Grid Search (0%, para dimensionar o efeito da regra) e a
    Selic real point-in-time (padrão do reporte). Nenhum parâmetro do sinal
    muda. No perfil futuros o funding permanece dentro (P&L do instrumento)."""
    close = serie["close"]
    escala_sinal = serie["escala_sinal"]
    selic_real = serie["selic_aa"]
    funding = serie["funding_d"] if perfil == "futuros" else None
    politicas_caixa = {"0pct": None, "selic_real": selic_real}
    resultado = {}
    for bps in GRID_CUSTOS_BPS:
        for rotulo_caixa, selic_arg in politicas_caixa.items():
            eq = simular_carteira(close, escala_sinal, bps / 10000.0, perfil,
                                  selic_arg, funding)["equity"]
            chave = f"custo_{bps}bps_caixa_{rotulo_caixa}"
            resultado[chave] = {
                periodo: {
                    "retorno_anualizado": calcular_metricas(janela(eq))["retorno_anualizado"],
                    "sortino_mar0": calcular_metricas(janela(eq))["sortino_mar0"],
                    "max_drawdown": calcular_metricas(janela(eq))["max_drawdown"],
                }
                for periodo, janela in (("in_sample", janela_is),
                                        ("out_of_sample", janela_oos))
            }
    return resultado


# ----------------------------------------------------------------------------
# Orquestração
# ----------------------------------------------------------------------------
def main() -> None:
    for perfil in PERFIS:
        serie = carregar_serie(perfil)
        print("\n" + "#" * 74)
        print(f"# PERFIL {perfil.upper()} — série congelada: "
              f"{serie.index[0].date()} -> {serie.index[-1].date()} ({len(serie)} dias)")
        print("#" * 74)

        analise = {
            "perfil": perfil,
            "janela": {"inicio": str(serie.index[0].date()),
                       "fim": str(serie.index[-1].date()), "dias": int(len(serie))},
            "retornos_anuais": retornos_anuais(serie),
            "janelas_de_crise": janelas_de_crise(serie),
            "information_ratio": information_ratio(serie),
            "distribuicao_e_whipsaw": distribuicao_e_whipsaw(serie),
            "payoff_extremos": payoff_extremos(serie),
            "benchmark_estatico_50_50": benchmark_estatico(serie),
            "sensibilidade_custo_caixa": sensibilidade_custo_caixa(serie, perfil),
        }
        with open(_arq_saida(perfil), "w") as f:
            json.dump(analise, f, indent=2, ensure_ascii=False)

        print(json.dumps(analise, indent=2, ensure_ascii=False))
        print(f"\nAnálise gravada em {_arq_saida(perfil)}")


if __name__ == "__main__":
    main()
