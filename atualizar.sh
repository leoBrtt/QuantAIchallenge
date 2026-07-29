#!/usr/bin/env bash
# ============================================================================
# CONTRAMARE — pipeline de um comando
# ============================================================================
# Uso:
#   ./atualizar.sh            atualiza a cauda dos dados, roda o motor e
#                             regenera os dois HTMLs
#   ./atualizar.sh --offline  pula o download e roda sobre o cache congelado
#   ./atualizar.sh --abrir    idem ao padrão, e abre o HTML no navegador
#
# O que NÃO muda ao rodar: os parâmetros do Grid Search. A janela In-Sample é
# truncada em 31/12/2022 (§6 do CLAUDE.md), então dados novos só esticam o
# Out-of-Sample — o protocolo one-shot continua respeitado.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
OFFLINE=0
ABRIR=0
for arg in "$@"; do
    case "$arg" in
        --offline) OFFLINE=1 ;;
        --abrir)   ABRIR=1 ;;
        *) echo "erro: argumento desconhecido '$arg' (use --offline ou --abrir)" >&2
           exit 2 ;;
    esac
done

if [ ! -x "$PY" ]; then
    echo "erro: ambiente virtual não encontrado em $PY" >&2
    echo "      crie com: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

# --- 1/3 · dados + motor -----------------------------------------------------
# Rede indisponível não deve derrubar o pipeline: o cache point-in-time (§4) é
# suficiente para reproduzir o backtest inteiro, só que sem os dias mais novos.
if [ "$OFFLINE" -eq 1 ]; then
    echo ">> modo offline: usando o cache congelado em dados/"
    "$PY" backtest.py
elif ! "$PY" backtest.py --atualizar; then
    echo >&2
    echo "AVISO: a atualização de dados falhou (rede ou API fora do ar)." >&2
    echo "       Refazendo o backtest sobre o cache congelado em dados/." >&2
    echo >&2
    "$PY" backtest.py
fi

# --- 2/3 · análise pós-OOS ---------------------------------------------------
# Grava o relatório legível em arquivo (antes ia para /dev/null e se perdia).
"$PY" analise_resultados.py > resultados/analise_resultados.txt

# --- 3/3 · gráficos ----------------------------------------------------------
"$PY" gerar_graficos.py

# --- resumo ------------------------------------------------------------------
ULTIMO_DIA=$("$PY" -c "
import pandas as pd
print(pd.read_csv('resultados/serie_backtest_spot.csv', index_col=0).index[-1][:10])
")

echo
echo "=========================================================================="
echo "Pronto — série avaliada até ${ULTIMO_DIA} (perfis spot e futuros)."
echo
echo "  backtest_spot.html / backtest_futuros.html      painéis principais (§7)"
echo "  resultados/heatmap_robustez_{spot,futuros}.html superfícies do Grid (§6)"
echo "  resultados/analise_resultados.txt               análise pós-OOS legível"
echo "  resultados/analise_resultados_{spot,futuros}.json  números p/ o relatório"
echo
echo "ATENÇÃO: os números de RELATORIO.md são fixos no texto e NÃO são"
echo "regenerados por este script. Depois de atualizar os dados, confira as"
echo "tabelas do Out-of-Sample contra resultados/metricas_{spot,futuros}.json"
echo "antes de entregar."
echo "=========================================================================="

if [ "$ABRIR" -eq 1 ]; then
    xdg-open backtest_spot.html >/dev/null 2>&1 &
    xdg-open backtest_futuros.html >/dev/null 2>&1 &
fi
