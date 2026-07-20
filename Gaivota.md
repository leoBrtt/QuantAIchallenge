# AUTOAVALIAÇÃO HONESTA — PROJETO CONTRAMARÉ × MANUAL DE AVALIAÇÃO OFICIAL
### Desafio Quant AI 2026 (Itaú Asset) · v2, atualizada em 20/07/2026 (revisão da autoavaliação de 17/07, após o fechamento das lacunas)

Este documento responde, critério a critério, à pergunta: **"o trabalho, como está hoje, atende ao que a banca procura?"** — usando o Manual de Avaliação Oficial como régua e as saídas congeladas do motor como evidência. A primeira versão (17/07) encontrou ~25% da nota descoberta e uma análise de resultados rasa; esta versão audita o estado **após** o plano de ação ser executado. Nada aqui foi retocado: os números desfavoráveis seguem reportados com o mesmo destaque que os favoráveis — vários deles, aliás, agora estão publicados no próprio relatório por iniciativa nossa.

---

## Veredito geral (resposta direta)

**O trabalho, como entrega, está fechado.** Os dois critérios de maior rigor (Modelagem 20% + Backtest 15%) seguem no nível que o Manual descreve como desempenho superior — replicável, transparente, com vieses mitigados e auditados. As três lacunas da v1 foram fechadas com artefatos concretos: a Análise de Resultados deixou de ser descritiva (Seções 9.1–9.6 do relatório: ano a ano, crises, IR canônico, atribuição sinal×exposição, autópsia do sinal), a Conclusão existe e é proporcional às evidências (Seção 12, incluindo "o que NÃO ficou demonstrado"), e o uso de IA está documentado fase a fase com os erros da própria IA (`USO_DE_IA.md`). A identidade CONTRAMARÉ foi unificada em todos os artefatos, com frase de mandato.

| # | Critério | Peso | Situação | Síntese |
|---|---|---:|:---:|---|
| 4.1 | Apresentação do robô | 5% | 🟢 | CONTRAMARÉ unificado em relatório, HTMLs e documentos + frase de mandato |
| 4.2 | Conceito da estratégia | 20% | 🟢 | Fenômeno, justificativa e forma de teste completos; tese reposicionada como mandato de risco; fragilidade do lado "euforia" declarada e quantificada |
| 4.3 | Modelagem | 20% | 🟢 | Estruturada, replicável, 4 parâmetros; inércia, whipsaw e limitação do FNG agora declarados no relatório |
| 4.4 | Backtest | 15% | 🟢 | 13 blindagens auditadas + sensibilidade custo (10/25/50 bps) × caixa (0/3/5%) |
| 4.5 | Análise dos resultados | 15% | 🟢 | Ano a ano, janelas de crise, IR canônico, atribuição e payoff dos extremos — incorporados ao relatório (Seção 9) |
| 4.6 | Conclusão e próximos passos | 10% | 🟢 | Seção 12: demonstrado vs. não demonstrado + 5 próximos passos com protocolo |
| 4.7 | Uso de IA generativa | 15% | 🟢 | `USO_DE_IA.md`: papel fase a fase, artefatos-prova, 6 casos de erro/contenção da IA |

---

## 4.1 Apresentação do Robô (5%) — 🟢 fechado

**O que temos.** Identidade única: **CONTRAMARÉ** no título do relatório, no `<title>` e `<h1>` do `backtest_resultado.html` e do `resultados/heatmap_robustez.html` (regenerados), no `Explicação.md` e no `USO_DE_IA.md`. A frase de mandato abre o painel e o relatório: *"CONTRAMARÉ não promete vencer o Bitcoin em retorno — promete entregar uma fração controlada do risco dele."* Ela cumpre dupla função: identidade conceitual e preparação da banca para a leitura correta do OOS. O nome é coerente com a tese (operar contra a maré do sentimento) — passa no teste de "coerência entre o nome e a estratégia" do Manual. Este arquivo (`Gaivota.md`) é o codinome interno da autoavaliação, não uma segunda identidade do robô — e está listado como tal na tabela de artefatos do relatório.

**Risco residual de defesa:** nenhum estrutural. Se houver apresentação oral/slides, abrir com a frase de mandato.

---

## 4.2 Conceito da Estratégia (20%) — 🟢 fechado (com honestidade estrutural)

**O que temos.** Os três itens que o Manual exige explicitamente estão articulados (em `Explicação.md` e no relatório): o **fenômeno** (sobre-reação de preço e sentimento em cripto), a **justificativa** (comportamental: manada/euforia e pânico geram desvios temporários revertíveis) e a **forma de teste** (Z-Score móvel do score combinado → escala de exposição, IS/OOS com one-shot). A restrição `Peso_Mayer + Peso_FNG = 1` e os cortes simétricos mostram desenho anti-overfitting **no nível conceitual**. A tese foi **reposicionada nos documentos como mandato de risco** (Seção 2 do relatório): o objetivo primário é assimetria de drawdown com fração do risco, e o custo assumido a priori é abrir mão de upside em bulls — o que o OOS confirmou.

**O que mudou desde a v1.** A fragilidade empírica do lado "vender na euforia" não está mais escondida numa autoavaliação: está **publicada e quantificada no relatório** (Seção 9.6), com nuance nova que a v1 não tinha — o sinal de euforia *acerta* o recuo médio dos 30 dias seguintes (−2,5%) e só "erra" nos horizontes de 90–180d (+20%/+39% médios), onde o momentum domina. A leitura "vende cedo demais" virou material de defesa, com a consequência tirada: cortes assimétricos ficam como pesquisa futura com protocolo próprio (Seção 12).

**Risco residual de defesa (não corrigível, apenas assumível):** originalidade moderada — Mayer e FNG são indicadores de varejo conhecidos. Defesa preparada: simplicidade deliberada (princípio de Neutralidade de Complexidade do Manual); a originalidade está na **arquitetura de decisão** (combinação, Z-Score móvel que remove limiares arbitrários, escala de 7 níveis, protocolo anti-snooping), não nos ingredientes.

---

## 4.3 Modelagem (20%) — 🟢 forte, fragilidades agora publicadas

**O que temos.** Todos os itens da rubrica: entradas definidas (BTC-USD + FNG, com datas e limitações declaradas), processamento descrito passo a passo (`Explicação.md` — cálculo e **motivo** de cada decisão), saída objetiva e testável (regra de rebalanceamento em 7 níveis, `w_BTC = (Escala+3)/6`), processo 100% sistemático e replicável (reprodutibilidade bit a bit verificada). Apenas 4 parâmetros livres, todos otimizados por protocolo declarado.

**O que mudou desde a v1.** As três fragilidades que a banca perspicaz acharia estão agora no próprio relatório, achadas por nós primeiro:
- **Inércia:** 75,5% do tempo no nível 0; extremos somam ~10% — publicado na Seção 9.5, com a atribuição da Seção 9.4 respondendo à pergunta inevitável ("e um 50/50 sem sinal?"): no IS o sinal quase dobra retorno e Sortino da base estática com exposição média até menor; no OOS a base derivante vence, mas deixando de ser o produto (beta 0,85, DD −49%).
- **Whipsaw:** 534 rebalanceamentos (~65/ano), 31% saltando ≥2 níveis; custo de 1,7–2,0 p.p./ano — Seção 9.5, com a frase "cortes largos reduzem churn" devidamente nuançada na Seção 5 (verdadeira só em relação a cortes mais estreitos). O erro factual da v1.0 do relatório ("~164 rebalanceios/ano no IS") foi corrigido: são ~60/ano no IS e ~72/ano no OOS.
- **Dependência do FNG:** metodologia não versionada pelo provedor — declarada como limitação nº 5 (Seção 11), com a mitigação (cache point-in-time) e o risco residual explícitos.

---

## 4.4 Backtest (15%) — 🟢 o ponto mais forte do trabalho

**O que temos.** Cada item da rubrica do Manual tem contrapartida implementada e **auditada** (não apenas declarada): implementação própria (`backtest.py`), coerência modelo↔simulação (o benchmark passa pelo mesmo motor), período justificado (máximo histórico disponível do FNG, warm-up excluído dos dois lados), mitigação de vieses verificada dia a dia — T+1 exato, causalidade do Z-Score provada por igualdade IS ≡ full-sample, custos dentro do loop de otimização, protocolo one-shot cumprido (a Seção 8.2 reporta a derrota no OOS sem retoque — a melhor evidência de que o protocolo foi respeitado). Início da janela ditado pelos dados (primeiro Z-Score válido), não por conveniência.

**O que mudou desde a v1.** A mini-tabela de sensibilidade sugerida existe (Seção 10): custo 10/25/50 bps × caixa 0/3/5% a.a., com sinal congelado e grade fixada a priori em `analise_resultados.py`. Ela produziu inclusive um número desfavorável que decidimos publicar: **a 50 bps o Sortino IS (0,21) cai abaixo do B&H (0,27)** — a viabilidade pressupõe execução a até ~25 bps, e isso está escrito no relatório.

**Risco residual de defesa:** slippage/spread além da taxa fixa não modelados (declarado, Seção 11); ~1,5 ciclo de BTC no IS (declarado desde a v1).

---

## 4.5 Análise dos Resultados (15%) — 🟢 fechado

Tudo o que a v1 apontou como faltante foi **recalculado sobre o cache atualizado (até 20/07) e incorporado ao relatório**, com fonte congelada em `resultados/analise_resultados.json`:

- **(a) Comportamento ao longo do tempo** — tabela ano a ano líquida (Seção 9.1): proteção nos três bears (2018 −31,6% vs. −59,6%; 2022 −26,2% vs. −64,3%; 2026 YTD −11,9% vs. −25,9%), upside parcial nos bulls, e o ⚠️ de 2025 (**−11,2% vs. −6,3%** — único ano perdendo do benchmark, regime serrilhado com whipsaw) reportado com o mesmo destaque. Janelas de crise com datas declaradas (Seção 9.2): FTX −8,3% vs. −25,8% (proteção máxima: euforia detectável antes); COVID −39,8% vs. −51,9% (proteção só parcial: o Z-Score de 90d é lento por construção — limitação estrutural admitida).
- **(b) IR canônico** — pela nossa própria régua (`CLAUDE.md` §5): **IS −0,48 · OOS −1,14** (tracking error 37,5% / 25,0%). Publicado por iniciativa própria como "o número mais duro do projeto" (Seção 9.3), com a leitura correta: o mandato nunca foi retorno ativo; o que valida o desenho é a estabilidade do perfil (beta 0,51 idêntico IS→OOS, vol 26% vs. 47%, DD −33,6% vs. −53,1%).
- **(c) Atribuição sinal × exposição média** — o benchmark estático 50/50 (mesmo motor, sinal constante 0, regra fixada a priori, declarado como análise pós-OOS) existe e é a Seção 9.4. Resultado honesto em duas partes: o sinal **agrega inequivocamente no IS** (12,4% vs. 7,4% a.a.; Sortino 0,44 vs. 0,23; DD −45% vs. −67%, com exposição menor) e **perde para a base derivante no OOS** — porque a deriva transformou a base num quase-B&H (85% de exposição), abandonando o mandato. Nenhum parâmetro foi tocado.
- **(d) Payoff dos extremos** — Seção 9.6, com horizonte triplo (30/90/180d) que refinou o achado da v1: euforia acerta em 30d e erra de 90d em diante; pânico tem mediana ~0 em 90d mas +21% em 180d. É autópsia de sinal, não descrição de métrica.

**Risco residual de defesa:** nenhum item da rubrica descoberto. O conteúdo é desfavorável em partes — mas o critério avalia análise crítica, não resultado bonito.

---

## 4.6 Conclusão e Próximos Passos (10%) — 🟢 fechado

A Seção 12 do relatório formaliza, com a maturidade que o Manual pede ("evitar conclusões desproporcionais às evidências"):

1. **O que ficou demonstrado:** processo auditado e reprodutível; perfil de risco que generaliza (beta/exposição/vol estáveis IS→OOS, proteção nos três bears e no FTX); sinal agregando valor sobre a exposição estática no período de treino.
2. **O que NÃO ficou demonstrado** — em seção própria, com esse título: retorno ativo (IR negativo nos dois períodos); sinal de euforia como previsor além de ~30d; superioridade ajustada a risco no OOS.
3. **Síntese proporcional:** "CONTRAMARÉ é um produto de perfil de risco validado em processo, não uma máquina de alpha validada em resultado."
4. **Cinco próximos passos, cada um com o protocolo que o tornaria legítimo:** redesenho a priori do espaço de cortes (ótimo na borda), histerese anti-whipsaw, cortes assimétricos (motivados pela evidência 9.6), caixa remunerado na v2, target-vol fora do grid.

---

## 4.7 Uso de IA Generativa (15%) — 🟢 fechado

`USO_DE_IA.md` documenta o que a v1 apontou como "o gap mais barato e mais urgente": o papel da IA em **todas** as fases (contrato de comportamento via `CLAUDE.md`; pesquisa dirigida Qlib/PyPortfolioOpt com referências arquivo:linha; red team pré-código; implementação + auditoria independente dia a dia; auditoria visual programática; avaliadora adversarial na Fase 5), cada fase com artefato-prova. O ponto que o Manual mais valoriza — "compreensão do papel da IA" — está coberto pelos **6 casos documentados em que a IA errou, foi corrigida ou teve limites impostos** (nomenclatura do Qlib; N=252 inaplicável; o erro factual dos "~164 rebalanceios/ano" pego por auditoria posterior; target-vol vetado; identidade dupla detectada; e o one-shot cumprido contra a tentação de re-tuning) e pelas 3 camadas de validação (programática, numérica, humana). O risco de "uso superficial ou meramente declaratório" não se aplica; o risco oposto (uso profundo não declarado) foi eliminado.

---

## O que deliberadamente NÃO foi feito, mesmo havendo tempo

Reotimizar parâmetros, ampliar o grid (o ótimo na borda `b3 = 2,00` fica como limitação declarada), trocar a função-objetivo, ou reexecutar o OOS com qualquer variação do sinal. O one-shot já foi consumido; qualquer uma dessas ações converteria nossa maior força (rigor de protocolo) na maior fraqueza (re-tuning disfarçado). Tudo o que foi adicionado desde a v1 é **análise, documentação e benchmarks com regras fixadas a priori** (`analise_resultados.py` lê apenas saídas congeladas) — nenhuma linha tocou os parâmetros congelados nem o motor.

## Riscos residuais consolidados (o que ainda pode custar pontos, e a defesa pronta)

| Risco | Defesa preparada |
|---|---|
| "A estratégia perdeu do B&H no OOS, inclusive em Sortino" | Mandato de risco declarado a priori na tese (Seção 2); perfil generalizou (beta 0,51 estável); reportado sem retoque — evidência de protocolo respeitado |
| "Mayer e FNG são indicadores de varejo" | Simplicidade deliberada (princípio do Manual); originalidade na arquitetura de decisão |
| "O robô fica 75% do tempo parado em 50/50" | Publicado por nós (9.5) + atribuição provando o valor do timing no IS (9.4) |
| "O ótimo caiu na borda do grid" | Limitação nº 1 declarada + próximo passo com protocolo (12) |
| "2025 foi pior que o benchmark" | Publicado com ⚠️ e explicado (whipsaw em mercado serrilhado, 9.1) |

---

*Fontes dos números deste documento: `resultados/metricas.json`, `resultados/analise_resultados.json`, `resultados/serie_backtest.csv` e `resultados/grid_search_is.csv` (saídas congeladas de `backtest.py` + `analise_resultados.py`, cache até 20/07/2026). Réguas: Manual de Avaliação Oficial (Criterios_Avaliacao_Desafio.pdf) e `CLAUDE.md` §1–§7. Autoavaliação v1 (17/07) preservada no histórico git (commit 258998c).*
