# -*- coding: utf-8 -*-
"""
FASE 4 — AUDITORIA VISUAL (Plotly) — Desafio Quant AI 2026 (Itaú Asset)
=======================================================================
Consome as saídas do `backtest.py` (nunca recalcula nada — o motor é a única
fonte de verdade) e exporta dois HTMLs autocontidos (plotly.js embutido,
funcionam offline para a banca):

  backtest_resultado.html          Entregável do CLAUDE.md §7:
                                   - Painel superior: Preço BTC (log) + SMA 200
                                     + marcadores dos rebalanceamentos;
                                   - Painel inferior: Equity da estratégia (com
                                     e sem custos) vs. Buy & Hold + área de
                                     alocação BTC/Caixa (eixo secundário);
                                   - Crosshair único sincronizado entre painéis
                                     (hoversubplots="axis") com tooltip limpo;
                                   - Tabela de métricas IS/OOS (§5) no topo.

  resultados/heatmap_robustez.html Material de defesa (§6): superfície do
                                   Sortino IS em dois cortes pela vizinhança
                                   do ótimo (parâmetros congelados).

Insumos (gerados por `python backtest.py`):
  resultados/serie_backtest.csv, resultados/metricas.json,
  resultados/parametros_otimos.json, resultados/grid_search_is.csv
"""

from __future__ import annotations

import json
import os
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DIR_RESULTADOS = "resultados"
ARQ_SERIE = os.path.join(DIR_RESULTADOS, "serie_backtest.csv")
ARQ_METRICAS = os.path.join(DIR_RESULTADOS, "metricas.json")
ARQ_PARAMS = os.path.join(DIR_RESULTADOS, "parametros_otimos.json")
ARQ_GRID = os.path.join(DIR_RESULTADOS, "grid_search_is.csv")
ARQ_SAIDA = "backtest_resultado.html"
ARQ_HEATMAP = os.path.join(DIR_RESULTADOS, "heatmap_robustez.html")

FIM_IN_SAMPLE = pd.Timestamp("2022-12-31")

# ----------------------------------------------------------------------------
# TOKENS DE DESIGN — paleta validada com scripts/validate_palette.js (dataviz):
# categóricas #2a78d6 / #eb6834 / #199e70 passam todos os checks (banda de
# luminância, croma, ΔE CVD >= 8, piso normal >= 15, contraste >= 3:1) sobre a
# superfície #fcfcfb. A curva "sem custos" é a MESMA entidade da estratégia:
# mesmo azul, tracejado (identidade pela linha, não por um 4º matiz).
# Verde/vermelho de rebalanceio são cores de ESTADO (status), com forma
# (triângulo ↑/↓) como codificação secundária — nunca cor sozinha.
# ----------------------------------------------------------------------------
COR = {
    "surface": "#fcfcfb", "page": "#f9f9f7",
    "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "axis": "#c3c2b7", "borda": "rgba(11,11,11,0.10)",
    "estrategia": "#2a78d6",           # slot 1 (azul)
    "buyhold": "#eb6834",              # slot 6 (laranja)
    "alocacao": "#199e70",             # aqua (passo escuro, contraste >= 3:1)
    "rebal_up": "#0ca30c",             # status good  (aumentou exposição)
    "rebal_down": "#d03b3b",           # status critical (reduziu exposição)
    "div_neg": "#d03b3b", "div_mid": "#f0efec", "div_pos": "#2a78d6",
}
FONTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'


# ============================================================================
# FORMATAÇÃO pt-BR (vírgula decimal; None -> "N/A" — guarda numérica do §5)
# ============================================================================
def _ptbr(txt: str) -> str:
    return txt.replace(",", "\0").replace(".", ",").replace("\0", ".")


def fmt_num(v, casas: int = 2) -> str:
    return "N/A" if v is None else _ptbr(f"{v:,.{casas}f}")


def fmt_pct(v, casas: int = 1, sinal: bool = False) -> str:
    if v is None:
        return "N/A"
    return _ptbr(f"{v:+.{casas}%}" if sinal else f"{v:.{casas}%}")


def fmt_data(ts) -> str:
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


# ============================================================================
# CARREGAMENTO (aborta com instrução clara se o motor ainda não rodou)
# ============================================================================
def carregar_saidas():
    faltando = [a for a in (ARQ_SERIE, ARQ_METRICAS, ARQ_PARAMS, ARQ_GRID)
                if not os.path.exists(a)]
    if faltando:
        raise FileNotFoundError(
            f"Saídas do motor não encontradas: {faltando}. "
            "Rode `python backtest.py` antes de gerar os gráficos.")

    serie = pd.read_csv(ARQ_SERIE, index_col="Date", parse_dates=True)
    grid = pd.read_csv(ARQ_GRID)
    with open(ARQ_METRICAS, encoding="utf-8") as f:
        metricas = json.load(f)
    with open(ARQ_PARAMS, encoding="utf-8") as f:
        params = json.load(f)
    return serie, metricas, params, grid


# ============================================================================
# FIGURA PRINCIPAL — 2 painéis empilhados sobre UM único eixo X
# (todos os traces em xaxis "x" => hoversubplots="axis" produz um crosshair
#  e um tooltip unificados que atravessam os dois painéis)
# ============================================================================
def montar_figura(serie: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    # ---------- Painel superior (yaxis): preço, SMA 200, rebalanceios ----------
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie["sma200"], name="SMA 200",
        yaxis="y", mode="lines",
        line=dict(color=COR["muted"], width=1.5),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie["close"], name="Preço BTC",
        yaxis="y", mode="lines",
        line=dict(color=COR["ink"], width=2),
        hovertemplate="Preço BTC: <b>US$ %{y:,.0f}</b><extra></extra>",
    ))

    # Rebalanceios: dias exatos em que a escala mudou de nível (execução T+1).
    esc, esc_ant = serie["escala_exec"], serie["escala_exec"].shift(1)
    rebal = serie["rebalanceou"].astype(bool)
    # Marcadores deslocados ±7% da linha de preço (offset multiplicativo, válido
    # em escala log): o dia exato fica no eixo X; o preço não é encoberto.
    for nome, mascara, simbolo, cor, desloc in (
            ("Rebalanceio ↑ BTC", rebal & (esc > esc_ant), "triangle-up", COR["rebal_up"], 0.93),
            ("Rebalanceio ↓ BTC", rebal & (esc < esc_ant), "triangle-down", COR["rebal_down"], 1.075)):
        pontos = serie[mascara]
        cdata = np.column_stack([
            esc_ant[mascara], esc[mascara],
            (esc_ant[mascara] + 3) / 6, (esc[mascara] + 3) / 6])
        fig.add_trace(go.Scatter(
            x=pontos.index, y=pontos["close"] * desloc, name=nome,
            yaxis="y", mode="markers", customdata=cdata,
            marker=dict(symbol=simbolo, size=8, color=cor,
                        line=dict(color=COR["surface"], width=1.2)),  # anel de superfície
            hovertemplate=("Rebalanceio: escala %{customdata[0]:.0f} → "
                           "<b>%{customdata[1]:.0f}</b> · alvo BTC "
                           "%{customdata[2]:.0%} → <b>%{customdata[3]:.0%}</b>"
                           "<extra></extra>"),
        ))

    # ---------- Painel inferior (yaxis2 + yaxis3): alocação e equity ----------
    # Área de alocação primeiro (fica ao fundo), em eixo secundário 0–100%.
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie["w_btc"], name="Alocação BTC (eixo dir.)",
        yaxis="y3", mode="lines", customdata=1.0 - serie["w_btc"],
        line=dict(color="rgba(25,158,112,0.55)", width=1),
        fill="tozeroy", fillcolor="rgba(25,158,112,0.12)",
        hovertemplate=("Alocação: <b>%{y:.1%}</b> BTC · "
                       "%{customdata:.1%} Caixa<extra></extra>"),
    ))
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie["equity_bruta"], name="Estratégia s/ custos",
        yaxis="y2", mode="lines", opacity=0.65,
        line=dict(color=COR["estrategia"], width=1.6, dash="dash"),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie["equity_liq"], name="Estratégia (líquida)",
        yaxis="y2", mode="lines", customdata=serie["equity_liq"] - 1.0,
        line=dict(color=COR["estrategia"], width=2.2),
        hovertemplate=("Estratégia (líq.): <b>×%{y:.2f}</b> · "
                       "%{customdata:+.1%} acum.<extra></extra>"),
    ))
    fig.add_trace(go.Scatter(
        x=serie.index, y=serie["equity_bh_liq"], name="Buy & Hold (líq.)",
        yaxis="y2", mode="lines", customdata=serie["equity_bh_liq"] - 1.0,
        line=dict(color=COR["buyhold"], width=2),
        hovertemplate=("Buy & Hold: <b>×%{y:.2f}</b> · "
                       "%{customdata:+.1%} acum.<extra></extra>"),
    ))

    # ---------- Layout: eixos, crosshair unificado, botões, fronteira ----------
    eixo_base = dict(gridcolor=COR["grid"], gridwidth=1, zeroline=False,
                     linecolor=COR["axis"], linewidth=1,
                     tickfont=dict(size=11, color=COR["ink2"]),
                     title_font=dict(size=12, color=COR["ink2"]))
    x0, x1 = serie.index[0], serie.index[-1]
    pad = pd.Timedelta(days=30)

    fig.update_layout(
        height=820,
        paper_bgcolor=COR["surface"], plot_bgcolor=COR["surface"],
        font=dict(family=FONTE, size=12, color=COR["ink"]),
        separators=",.",                       # vírgula decimal, ponto de milhar
        margin=dict(l=70, r=70, t=170, b=52),
        hovermode="x unified", hoversubplots="axis",
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=COR["borda"],
                        font=dict(family=FONTE, size=12, color=COR["ink"])),
        legend=dict(orientation="h", x=0, xanchor="left",
                    y=1.03, yanchor="bottom",
                    font=dict(size=11, color=COR["ink2"])),
        xaxis=dict(eixo_base, domain=[0.0, 1.0], anchor="y2", showgrid=False,
                   ticks="outside", tickcolor=COR["axis"],
                   hoverformat="%d/%m/%Y",
                   tickformatstops=[
                       dict(dtickrange=[None, "M1"], value="%d/%m/%y"),
                       dict(dtickrange=["M1", "M12"], value="%m/%Y"),
                       dict(dtickrange=["M12", None], value="%Y")],
                   showspikes=True, spikemode="across", spikesnap="cursor",
                   spikecolor=COR["muted"], spikethickness=1, spikedash="dot"),
        yaxis=dict(eixo_base, domain=[0.56, 1.0], type="log",
                   title=dict(text="Preço BTC (US$, log)"),
                   tickvals=[5_000, 10_000, 20_000, 40_000, 80_000, 160_000],
                   ticktext=["5 mil", "10 mil", "20 mil", "40 mil", "80 mil", "160 mil"]),
        yaxis2=dict(eixo_base, domain=[0.0, 0.44],
                    title=dict(text="Equity (base 1,0)"), tickprefix="×"),
        # range [0, 2.6] comprime a faixa de alocação no terço inferior do
        # painel (estilo "volume"): as curvas de equity ficam desobstruídas.
        yaxis3=dict(overlaying="y2", side="right", range=[0, 2.6],
                    showgrid=False, zeroline=False,
                    tickvals=[0, 0.5, 1.0], tickformat=".0%",
                    tickfont=dict(size=11, color=COR["alocacao"]),
                    title=dict(text="Alocação BTC",
                               font=dict(size=12, color=COR["alocacao"]))),
        updatemenus=[
            dict(type="buttons", direction="right",
                 x=0, xanchor="left", y=1.20, yanchor="top",
                 bgcolor=COR["surface"], bordercolor=COR["axis"], borderwidth=1,
                 font=dict(size=11, color=COR["ink2"]), pad=dict(l=2, r=2),
                 buttons=[
                     dict(label="Período completo", method="relayout",
                          args=[{"xaxis.autorange": True}]),
                     dict(label="In-Sample (treino)", method="relayout",
                          args=[{"xaxis.range": [str((x0 - pad).date()),
                                                 str(FIM_IN_SAMPLE.date())],
                                 "xaxis.autorange": False}]),
                     dict(label="Out-of-Sample (one-shot)", method="relayout",
                          args=[{"xaxis.range": [str(FIM_IN_SAMPLE.date()),
                                                 str((x1 + pad).date())],
                                 "xaxis.autorange": False}]),
                 ]),
            dict(type="buttons", direction="right",
                 x=1, xanchor="right", y=1.20, yanchor="top",
                 bgcolor=COR["surface"], bordercolor=COR["axis"], borderwidth=1,
                 font=dict(size=11, color=COR["ink2"]), pad=dict(l=2, r=2),
                 buttons=[
                     dict(label="Log", method="relayout",
                          args=[{"yaxis.type": "log"}]),
                     dict(label="Linear", method="relayout",
                          args=[{"yaxis.type": "linear"}]),
                 ]),
        ],
    )

    # Fronteira IS/OOS (31/12/2022) atravessando os dois painéis.
    fig.add_shape(type="line", xref="x", yref="paper",
                  x0=FIM_IN_SAMPLE, x1=FIM_IN_SAMPLE, y0=0, y1=1,
                  line=dict(color=COR["muted"], width=1, dash="dot"))
    anot = dict(yref="paper", y=1.0, yanchor="top", showarrow=False,
                font=dict(size=11, color=COR["ink2"]),
                bgcolor="rgba(252,252,251,0.85)")
    fig.add_annotation(anot, x=FIM_IN_SAMPLE, xanchor="right", xshift=-8,
                       text="In-Sample (treino)")
    fig.add_annotation(anot, x=FIM_IN_SAMPLE, xanchor="left", xshift=8,
                       text="Out-of-Sample (one-shot)")

    # Rótulos de painel + rótulos diretos no fim das curvas de equity.
    rotulo = dict(xref="paper", x=0.004, xanchor="left", yref="paper",
                  yanchor="top", showarrow=False,
                  font=dict(size=11, color=COR["muted"]))
    fig.add_annotation(rotulo, y=0.998, text="PREÇO & EXECUÇÃO")
    fig.add_annotation(rotulo, y=0.435, text="PERFORMANCE & ALOCAÇÃO")
    for coluna in ("equity_liq", "equity_bh_liq"):
        fig.add_annotation(x=x1, y=float(serie[coluna].iloc[-1]),
                           xref="x", yref="y2", xanchor="left", xshift=6,
                           yanchor="middle", showarrow=False,
                           font=dict(size=11, color=COR["ink2"]),
                           text=_ptbr(f"×{serie[coluna].iloc[-1]:.2f}"))
    return fig


# ============================================================================
# TABELA DE MÉTRICAS (HTML) — §5: 6 métricas + Beta bônus, N/A explícito
# ============================================================================
LINHAS_METRICAS = [
    ("Retorno anualizado", "retorno_anualizado", "pct"),
    ("Volatilidade anualizada", "volatilidade_anualizada", "pct"),
    ("Sharpe (rf=0)", "sharpe_rf0", "num"),
    ("Sortino (MAR=0)", "sortino_mar0", "num"),
    ("Calmar", "calmar", "num"),
    ("Max Drawdown", "max_drawdown", "pct"),
]


def tabela_metricas_html(metricas: dict) -> str:
    cards = []
    for chave, titulo in (("in_sample", "In-Sample · treino"),
                          ("out_of_sample", "Out-of-Sample · one-shot")):
        m = metricas[chave]
        periodo = f"{fmt_data(m['inicio'])} → {fmt_data(m['fim'])}"
        linhas = []
        for rotulo, campo, tipo in LINHAS_METRICAS:
            fmt = (lambda v: fmt_pct(v, 2, sinal=True)) if tipo == "pct" else fmt_num
            linhas.append(
                f"<tr><td>{rotulo}</td>"
                f"<td class='num destaque'>{fmt(m['estrategia_liquida'][campo])}</td>"
                f"<td class='num'>{fmt(m['estrategia_bruta'][campo])}</td>"
                f"<td class='num'>{fmt(m['buy_hold_liquido'][campo])}</td></tr>")
        linhas.append(
            f"<tr><td>Beta vs. Buy &amp; Hold <span class='bonus'>bônus</span></td>"
            f"<td class='num destaque'>{fmt_num(m['beta_vs_buy_hold'])}</td>"
            f"<td class='num'>—</td><td class='num'>1,00</td></tr>")
        linhas.append(
            f"<tr><td>Exposição média a BTC</td>"
            f"<td class='num destaque'>{fmt_pct(m['exposicao_media_btc'])}</td>"
            f"<td class='num'>—</td><td class='num'>100,0%</td></tr>")
        linhas.append(
            f"<tr><td>Rebalanceamentos</td>"
            f"<td class='num destaque'>{m['n_rebalanceios']}</td>"
            f"<td class='num'>—</td><td class='num'>1</td></tr>")
        cards.append(f"""
      <section class="card">
        <h2>{titulo}</h2>
        <p class="periodo">{periodo} · atribuição pela data do retorno</p>
        <table>
          <thead><tr><th>Métrica</th><th class="num">Estratégia (líq.)</th>
              <th class="num">Estratégia (s/ custos)</th><th class="num">Buy &amp; Hold (líq.)</th></tr></thead>
          <tbody>{''.join(linhas)}</tbody>
        </table>
      </section>""")
    return "".join(cards)


# ============================================================================
# PÁGINA HTML (autocontida, tema claro institucional único — documento de banca)
# ============================================================================
CSS = f"""
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ background: {COR['page']}; color: {COR['ink']};
         font-family: {FONTE}; font-size: 14px; padding: 24px;
         max-width: 1240px; margin: 0 auto; }}
  header.card h1 {{ font-size: 20px; font-weight: 650; }}
  .sub {{ color: {COR['ink2']}; font-size: 13px; margin-top: 6px; line-height: 1.5; }}
  .card {{ background: {COR['surface']}; border: 1px solid {COR['borda']};
          border-radius: 10px; padding: 18px 20px; margin-bottom: 16px; }}
  .grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(430px, 1fr));
           gap: 16px; margin-bottom: 16px; }}
  .grade .card {{ margin-bottom: 0; }}
  h2 {{ font-size: 14px; font-weight: 650; }}
  .periodo {{ color: {COR['muted']}; font-size: 12px; margin: 4px 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ color: {COR['ink2']}; font-weight: 600; text-align: left;
       border-bottom: 1px solid {COR['axis']}; padding: 6px 8px; }}
  td {{ padding: 6px 8px; border-bottom: 1px solid {COR['grid']}; }}
  tr:last-child td {{ border-bottom: none; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .destaque {{ font-weight: 650; }}
  .bonus {{ color: {COR['muted']}; font-size: 11px; font-weight: 400; }}
  .periodo-card {{ position: sticky; top: 10px; z-index: 5;
                  box-shadow: 0 8px 22px rgba(11,11,11,0.07); }}
  .periodo-topo {{ display: flex; justify-content: space-between;
                  align-items: flex-start; gap: 16px; flex-wrap: wrap;
                  margin-bottom: 4px; }}
  .capital-label {{ display: flex; align-items: center; gap: 8px;
                   color: {COR['ink2']}; font-size: 12px; white-space: nowrap; }}
  #capital-inicial {{ width: 110px; text-align: right; font: inherit;
                     font-variant-numeric: tabular-nums; color: {COR['ink']};
                     background: {COR['surface']}; border: 1px solid {COR['axis']};
                     border-radius: 6px; padding: 4px 8px; }}
  .chip {{ display: inline-block; width: 14px; height: 0; border-top: 3px solid;
          border-radius: 2px; margin-right: 7px; vertical-align: middle; }}
  .chip.tracejada {{ border-top-style: dashed; border-top-width: 2px; }}
  footer.card ul {{ margin: 8px 0 0 18px; color: {COR['ink2']};
                   font-size: 12.5px; line-height: 1.7; }}
  .plotly-card {{ padding: 8px 10px; }}
"""


def painel_periodo_html(serie: pd.DataFrame) -> str:
    """Cartão sticky "Desempenho na janela selecionada": reage ao zoom/seleção
    do gráfico (evento `plotly_relayout`) e rebaseia as três séries num capital
    inicial comum no primeiro dia da janela visível — assim o desempenho da
    estratégia e do Buy & Hold é comparável em qualquer recorte de tempo.
    Mostra capital inicial, capital final, retorno do período e retorno
    anualizado (N=365, geométrico — mesma convenção do §5). Só LÊ as curvas
    de equity já congeladas pelo motor — nenhuma métrica é recalculada."""
    dados = {
        "datas": [d.strftime("%Y-%m-%d") for d in serie.index],
        "series": {chave: [round(float(v), 6) for v in serie[coluna]]
                   for chave, coluna in (("liq", "equity_liq"),
                                         ("bruta", "equity_bruta"),
                                         ("bh", "equity_bh_liq"))},
    }
    linhas = []
    for chave, chip, nome in (
            ("liq", f'<span class="chip" style="border-color:{COR["estrategia"]}"></span>',
             "Estratégia (líquida)"),
            ("bruta", f'<span class="chip tracejada" style="border-color:{COR["estrategia"]}"></span>',
             "Estratégia s/ custos"),
            ("bh", f'<span class="chip" style="border-color:{COR["buyhold"]}"></span>',
             "Buy &amp; Hold (líq.)")):
        classe = " destaque" if chave == "liq" else ""
        linhas.append(
            f"<tr><td>{chip}{nome}</td>"
            + "".join(f"<td class='num{classe}' id='{chave}-{campo}'>—</td>"
                      for campo in ("antes", "depois", "ret", "aa")) + "</tr>")

    return f"""
  <section class="card periodo-card">
    <div class="periodo-topo">
      <div>
        <h2>Desempenho na janela selecionada</h2>
        <p class="periodo" id="periodo-datas">—</p>
      </div>
      <label class="capital-label">Capital inicial (US$)
        <input id="capital-inicial" inputmode="numeric" value="100.000">
      </label>
    </div>
    <table>
      <thead><tr><th>Série</th><th class="num">Capital inicial</th>
        <th class="num">Capital final</th>
        <th class="num">Retorno no período</th><th class="num">Retorno anualizado</th></tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table>
    <p class="sub">Arraste uma área sobre o gráfico (zoom), use os botões de período
    ou dê duplo clique para voltar à janela completa — a tabela acompanha a janela
    exibida. As três séries partem do <b>mesmo capital inicial</b> no primeiro dia
    da janela visível, permitindo comparar diretamente o desempenho da estratégia
    e do Buy &amp; Hold em qualquer recorte de tempo. Anualização geométrica N=365;
    janelas &lt; 30 dias não são anualizadas (—).</p>
  </section>
  <script id="dados-periodo" type="application/json">{json.dumps(dados, separators=(',', ':'))}</script>
  <script>
  (function () {{
    "use strict";
    var D = JSON.parse(document.getElementById("dados-periodo").textContent);
    var T = D.datas.map(function (s) {{ return Date.parse(s + "T00:00:00Z"); }});
    var fmtUSD = new Intl.NumberFormat("pt-BR",
        {{style: "currency", currency: "USD", maximumFractionDigits: 0}});
    var fmtPct = new Intl.NumberFormat("pt-BR",
        {{style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1,
          signDisplay: "exceptZero"}});
    function el(id) {{ return document.getElementById(id); }}
    function fmtDia(t) {{
      var d = new Date(t);
      return ("0" + d.getUTCDate()).slice(-2) + "/" +
             ("0" + (d.getUTCMonth() + 1)).slice(-2) + "/" + d.getUTCFullYear();
    }}
    function capital() {{
      var bruto = el("capital-inicial").value
          .replace(/\\./g, "").replace(",", ".").replace(/[^\\d.]/g, "");
      var v = parseFloat(bruto);
      return (isFinite(v) && v > 0) ? v : 100000;
    }}
    function parseData(v) {{
      return (typeof v === "number")
          ? v : Date.parse(String(v).slice(0, 10) + "T00:00:00Z");
    }}
    function janela(gd) {{
      var xa = (gd.layout || {{}}).xaxis || {{}};
      if (!xa.range || xa.autorange) return [T[0], T[T.length - 1]];
      return [parseData(xa.range[0]), parseData(xa.range[1])];
    }}
    function atualizar(gd) {{
      var faixa = janela(gd);
      var a = 0, b = T.length - 1;
      while (a < T.length - 1 && T[a] < faixa[0]) a++;
      while (b > 0 && T[b] > faixa[1]) b--;
      if (b - a < 1) return;               // janela precisa de >= 2 pontos
      var cap = capital();
      var dias = Math.round((T[b] - T[a]) / 864e5);
      el("periodo-datas").textContent =
          fmtDia(T[a]) + " \\u2192 " + fmtDia(T[b]) + " \\u00b7 " + dias + " dias" +
          ((a === 0 && b === T.length - 1) ? " \\u00b7 janela completa" : "");
      ["liq", "bruta", "bh"].forEach(function (s) {{
        var eq = D.series[s];
        var ret = eq[b] / eq[a] - 1;
        el(s + "-antes").textContent = fmtUSD.format(cap);
        el(s + "-depois").textContent = fmtUSD.format(cap * (eq[b] / eq[a]));
        el(s + "-ret").textContent = fmtPct.format(ret);
        el(s + "-aa").textContent = (dias >= 30)
            ? fmtPct.format(Math.pow(1 + ret, 365 / dias) - 1) : "\\u2014";
      }});
    }}
    function ligar() {{
      var gd = document.querySelector(".plotly-graph-div");
      if (!gd || typeof gd.on !== "function") {{ setTimeout(ligar, 120); return; }}
      gd.on("plotly_relayout", function () {{ atualizar(gd); }});
      el("capital-inicial").addEventListener("input", function () {{ atualizar(gd); }});
      atualizar(gd);
    }}
    ligar();
  }})();
  </script>"""


def montar_pagina(fig: go.Figure, metricas: dict, params: dict,
                  serie: pd.DataFrame) -> str:
    div_grafico = fig.to_html(
        full_html=False, include_plotlyjs=True,
        config={"displaylogo": False, "responsive": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
                "toImageButtonOptions": {"filename": "backtest_resultado",
                                         "scale": 2}})
    peso_m = params["peso_mayer"]
    subtitulo = (
        f"Parâmetros congelados no In-Sample (Grid Search, objetivo Sortino MAR=0): "
        f"Peso Mayer <b>{fmt_num(peso_m, 1)}</b> · Peso FNG <b>{fmt_num(1 - peso_m, 1)}</b> · "
        f"cortes do Z-Score <b>±{fmt_num(params['b1'])} / ±{fmt_num(params['b2'])} / "
        f"±{fmt_num(params['b3'])}</b><br>"
        f"Execução T+1 · custo 10 bps por rebalanceamento · caixa a 0% a.a. · "
        f"anualização N=365 · janela avaliada {fmt_data(serie.index[0])} → "
        f"{fmt_data(serie.index[-1])} (warm-up excluído)")

    notas = f"""
      <li><b>Convenção T+1 única:</b> sinal no fechamento de D, execução no fechamento
          de D+1 (custo debitado na execução), retorno capturado a partir de D+2 —
          idêntica para estratégia, Grid Search e benchmark Buy &amp; Hold.</li>
      <li><b>Curvas:</b> "líquida" = com custos de 10 bps por rebalanceamento;
          "s/ custos" = bruta. O Buy &amp; Hold é reportado líquido do custo de entrada
          e passa pelo mesmo motor (sinal constante +3), com a mesma data de início.</li>
      <li><b>Fronteira IS/OOS</b> em 31/12/2022 pela data do retorno; validação
          Out-of-Sample <b>one-shot</b> com parâmetros congelados; o rolling do Z-Score
          não é resetado na fronteira (janela causal olhando para trás não é leakage).</li>
      <li><b>Guardas numéricas (§5):</b> Sortino/Calmar com denominador zero são
          reportados como N/A — nunca substituídos por epsilon.</li>
      <li><b>Painel "Desempenho na janela selecionada":</b> lê exclusivamente as
          curvas de equity congeladas pelo motor (marcação a mercado dia a dia) e
          as rebaseia num capital inicial comum no primeiro dia da janela exibida —
          nenhuma métrica é recalculada; anualização geométrica N=365, idêntica
          ao motor.</li>
      <li><b>Caveat honesto (§6):</b> 2018–2022 contém ≈1,5 ciclo de BTC — poucas
          observações independentes. A robustez dos parâmetros é defendida pela
          vizinhança do ótimo: <code>resultados/heatmap_robustez.html</code>.</li>
      <li><b>Tabela-fonte (auditoria):</b> série diária completa em
          <code>resultados/serie_backtest.csv</code>; métricas em
          <code>resultados/metricas.json</code>.</li>"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtest — Estratégia Contrarian BTC/Caixa · Quant AI 2026</title>
<style>{CSS}</style>
</head>
<body>
  <header class="card">
    <h1>Estratégia Contrarian BTC/Caixa — Múltiplo de Mayer × Fear &amp; Greed</h1>
    <p class="sub">{subtitulo}</p>
  </header>
  <div class="grade">{tabela_metricas_html(metricas)}</div>
  <div>{painel_periodo_html(serie)}
  <section class="card plotly-card">{div_grafico}</section></div>
  <footer class="card">
    <h2>Notas metodológicas (blindagem anti-vieses)</h2>
    <ul>{notas}</ul>
    <p class="sub" style="margin-top:10px">Gerado em {fmt_data(date.today())} por
    <code>gerar_graficos.py</code> a partir das saídas congeladas de
    <code>backtest.py</code> (dados point-in-time em <code>dados/</code>).</p>
  </footer>
</body>
</html>"""


# ============================================================================
# HEATMAP DE ROBUSTEZ (§6) — dois cortes 2D pela vizinhança do ótimo
# ============================================================================
def montar_heatmap(grid: pd.DataFrame, params: dict) -> go.Figure:
    peso, b1o, b2o, b3o = (params["peso_mayer"], params["b1"],
                           params["b2"], params["b3"])
    grid = grid.copy()
    # Configurações descartadas (exposição < 25% ou métrica N/A) ficam em branco.
    grid.loc[grid["descartada"].astype(bool), "sortino_is"] = np.nan

    fatia_a = grid[(grid["b2"] == b2o) & (grid["b3"] == b3o)].pivot(
        index="b1", columns="peso_mayer", values="sortino_is")
    fatia_b = grid[(grid["peso_mayer"] == peso) & (grid["b3"] == b3o)].pivot(
        index="b2", columns="b1", values="sortino_is")

    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.14,
        subplot_titles=(
            _ptbr(f"peso Mayer × b1  (b2={b2o:.2f} · b3={b3o:.2f} fixos)"),
            _ptbr(f"b1 × b2  (peso Mayer={peso:.1f} · b3={b3o:.2f} fixos)")))

    hover_a = ("peso Mayer %{x:.1f} · b1 %{y:.2f}<br>"
               "Sortino IS: <b>%{z:.3f}</b><extra></extra>")
    hover_b = ("b1 %{x:.2f} · b2 %{y:.2f}<br>"
               "Sortino IS: <b>%{z:.3f}</b><extra></extra>")
    for col, fatia, hover in ((1, fatia_a, hover_a), (2, fatia_b, hover_b)):
        fig.add_trace(go.Heatmap(
            x=fatia.columns, y=fatia.index, z=fatia.values,
            coloraxis="coloraxis", xgap=2, ygap=2,   # vão de superfície entre células
            hovertemplate=hover), row=1, col=col)

    # Contorno na célula ótima de cada corte.
    for (xref, yref, xc, yc, dx, dy) in (("x", "y", peso, b1o, 0.05, 0.125),
                                         ("x2", "y2", b1o, b2o, 0.125, 0.125)):
        fig.add_shape(type="rect", xref=xref, yref=yref,
                      x0=xc - dx, x1=xc + dx, y0=yc - dy, y1=yc + dy,
                      line=dict(color=COR["ink"], width=2))
        fig.add_annotation(x=xc, y=yc + dy, xref=xref, yref=yref,
                           yshift=6, yanchor="bottom", text="ótimo",
                           showarrow=False,
                           font=dict(size=11, color=COR["ink"]))

    fig.update_layout(
        height=460,
        paper_bgcolor=COR["surface"], plot_bgcolor=COR["surface"],
        font=dict(family=FONTE, size=12, color=COR["ink"]),
        separators=",.", margin=dict(l=64, r=30, t=56, b=56),
        coloraxis=dict(
            cmid=0.0,   # divergente ancorado em Sortino = 0 (polaridade real)
            colorscale=[[0.0, COR["div_neg"]], [0.5, COR["div_mid"]],
                        [1.0, COR["div_pos"]]],
            colorbar=dict(title=dict(text="Sortino IS", font=dict(size=12)),
                          thickness=12, outlinewidth=0,
                          tickfont=dict(size=11, color=COR["ink2"]))),
    )
    eixos = dict(showgrid=False, zeroline=False, linecolor=COR["axis"],
                 tickfont=dict(size=11, color=COR["ink2"]),
                 title_font=dict(size=12, color=COR["ink2"]))
    fig.update_xaxes(eixos, title_text="peso Mayer", dtick=0.1, row=1, col=1)
    fig.update_yaxes(eixos, title_text="b1 (σ)", dtick=0.25, row=1, col=1)
    fig.update_xaxes(eixos, title_text="b1 (σ)", dtick=0.25, row=1, col=2)
    fig.update_yaxes(eixos, title_text="b2 (σ)", dtick=0.25, row=1, col=2)
    for anot in fig.layout.annotations[:2]:
        anot.font = dict(size=13, color=COR["ink2"])
    return fig


def montar_pagina_heatmap(fig: go.Figure, params: dict, grid: pd.DataFrame) -> str:
    div = fig.to_html(full_html=False, include_plotlyjs=True,
                      config={"displaylogo": False, "responsive": True})
    n_desc = int(grid["descartada"].astype(bool).sum())
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Robustez do Grid Search — Quant AI 2026</title>
<style>{CSS}</style>
</head>
<body>
  <header class="card">
    <h1>Robustez do Grid Search — superfície do objetivo (Sortino In-Sample)</h1>
    <p class="sub">Dois cortes 2D da superfície de {len(grid)} combinações pela
    vizinhança do ótimo congelado (peso Mayer {fmt_num(params['peso_mayer'], 1)};
    cortes ±{fmt_num(params['b1'])} / ±{fmt_num(params['b2'])} /
    ±{fmt_num(params['b3'])}). Leitura: superfície <b>plana</b> ao redor do ótimo
    = parâmetros robustos; <b>pico isolado</b> = suspeita de overfitting.
    Células em branco = configuração descartada pelas regras pré-declaradas
    (exposição média &lt; 25% ou métrica N/A) — {n_desc} descartes no grid completo.</p>
  </header>
  <section class="card plotly-card">{div}</section>
  <footer class="card">
    <h2>Observação para a defesa (registrada no ROADMAP, Fase 3)</h2>
    <ul>
      <li>O ótimo caiu na <b>borda superior</b> do espaço de cortes (b3 = 2,00 é o
      máximo do grid): a superfície cresce na direção de cortes mais largos
      (estratégia mais inerte). Ampliar o grid após observar o OOS flertaria com
      re-tuning — qualquer redesenho do espaço de busca exigiria justificativa
      a priori e nova rodada OOS única.</li>
      <li>Superfície completa (616 combinações, com descartes e motivos):
      <code>resultados/grid_search_is.csv</code>.</li>
    </ul>
  </footer>
</body>
</html>"""


# ============================================================================
# ORQUESTRAÇÃO
# ============================================================================
def main() -> None:
    print("[1/3] Lendo saídas congeladas do motor...")
    serie, metricas, params, grid = carregar_saidas()
    print(f"      {len(serie)} dias | {serie.index[0].date()} -> "
          f"{serie.index[-1].date()} | grid: {len(grid)} combinações")

    print("[2/3] Montando painel principal (2 painéis sincronizados + métricas)...")
    fig = montar_figura(serie)
    with open(ARQ_SAIDA, "w", encoding="utf-8") as f:
        f.write(montar_pagina(fig, metricas, params, serie))
    print(f"      -> {ARQ_SAIDA}")

    print("[3/3] Montando heatmap de robustez do Grid Search...")
    fig_hm = montar_heatmap(grid, params)
    with open(ARQ_HEATMAP, "w", encoding="utf-8") as f:
        f.write(montar_pagina_heatmap(fig_hm, params, grid))
    print(f"      -> {ARQ_HEATMAP}")


if __name__ == "__main__":
    main()
