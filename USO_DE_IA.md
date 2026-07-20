# USO DE IA GENERATIVA NO PROJETO CONTRAMARÉ
### Desafio Quant AI 2026 (Itaú Asset) — documentação do critério 4.7

A IA generativa (Claude, via Claude Code) foi usada de forma **estrutural — não decorativa — em todas as fases do projeto**, sempre no papel de co-piloto sob contrato de comportamento explícito, com a equipe definindo as regras, validando as saídas e mantendo a palavra final. Este documento registra, fase a fase: o papel da IA, o artefato que prova o uso, e — tão importante quanto — **onde a IA errou, foi corrigida ou teve limites impostos**.

## O contrato de comportamento: `CLAUDE.md` como regulamento da IA

Antes de qualquer código, a equipe converteu o regulamento do desafio e as decisões de arquitetura num contrato que **governa o comportamento da própria IA** (`CLAUDE.md`, §1–§7). Três cláusulas existem especificamente para conter modos de falha conhecidos de modelos generativos:

- **"Sem Alucinação Matemática"** (§1): a IA é proibida de "estimar" ou "sugerir" pesos de indicadores de cabeça — toda otimização é determinística, via Grid Search em código. A cláusula elimina o risco de números plausíveis-mas-inventados entrarem no modelo.
- **"Neutralidade de Complexidade"** (§1): veta a tendência de modelos generativos de propor soluções impressionantes (Deep Learning, RL) onde a banca pede transparência.
- **Convenções fechadas a priori** (§3–§6): T+1, N=365, guardas numéricas, protocolo one-shot — a IA implementa, não improvisa.

Esse desenho inverte a relação usual: em vez de a equipe revisar código de IA procurando vieses depois, os vieses foram **proibidos por escrito antes**, e as auditorias das fases seguintes verificam o cumprimento.

## Fase a fase

| Fase | Papel da IA | Artefato-prova |
|---|---|---|
| 1. Tese e arquitetura | Formalizar a tese contrarian (Mayer × FNG → Z-Score → escala de 7 níveis) em regulamento executável; estruturar as restrições anti-overfitting no nível conceitual (pesos somando 1, cortes simétricos, 4 parâmetros) | `CLAUDE.md` §2–§3, `ROADMAP.md` Fase 1 |
| 2. Pesquisa dirigida | Extrair boas práticas de dois repositórios de referência (Microsoft Qlib, PyPortfolioOpt) com citações arquivo:linha — cache point-in-time, custos dentro do loop, equity com/sem custos | `ROADMAP.md` Fase 2 (achados com referência a arquivo e linha em `referencias/`) |
| 2.5. Red team pré-código | Auditoria de estresse da arquitetura ANTES de programar, nos 4 eixos: data leakage, consistência matemática, data snooping, complexidade. Achados classificados por gravidade e convertidos em regras do `CLAUDE.md` (warm-up do FNG, guardas de divisão por zero, restrição anti-degenerada, não resetar o rolling na fronteira IS/OOS) | `ROADMAP.md` Fase 2.5 |
| 3. Implementação + auditoria | Gerar o motor (`backtest.py`, ~500 linhas legíveis) sob o regulamento; em seguida, **auditar o próprio código** com um script de verificação independente que testou as propriedades críticas dia a dia (T+1 exato, encadeamento do sinal, custos só na execução, causalidade do Z-Score por igualdade IS ≡ full-sample, reprodutibilidade bit a bit) | `backtest.py`, `RELATORIO_CONTRAMARE.md` Seções 3–4 |
| 4. Auditoria visual | Gerar o painel Plotly e auditar o resultado como artefato: paleta validada por verificador **programático** de daltonismo/contraste; layout iterado por screenshot headless até passar a revisão | `gerar_graficos.py`, `backtest_resultado.html`, `resultados/heatmap_robustez.html` |
| 5. Avaliadora adversarial | Autoavaliação do trabalho contra o Manual de Avaliação da banca, com a instrução de produzir os achados **desfavoráveis** com o mesmo destaque dos favoráveis — e a análise crítica pós-OOS (`analise_resultados.py`) que os quantifica | `Gaivota.md`, `analise_resultados.py`, `RELATORIO_CONTRAMARE.md` Seções 9–12 |

## Onde a IA errou, foi corrigida ou teve limites impostos

Uso profundo de IA sem supervisão seria um risco, não um mérito. Os casos abaixo são a evidência de que a supervisão funcionou:

1. **Nomenclatura herdada errada (Fase 2).** O Qlib chama `média/desvio·√N` de "Information Ratio" — que é, tecnicamente, um Sharpe com rf=0. O erro foi detectado na pesquisa e a nomenclatura corrigida no projeto inteiro; o IR **canônico** (sobre retornos ativos) foi depois calculado corretamente na Seção 9.3 do relatório — e é desfavorável à estratégia, o que reforça que a correção não foi cosmética.
2. **Anualização inaplicável (Fase 2).** As bibliotecas de referência anualizam com N=252 (ou 238) pregões — errado para um ativo que negocia 24/7. Convenção única N=365 imposta no `CLAUDE.md` §5.
3. **Erro factual da IA no relatório, pego por auditoria posterior (Fase 5).** A v1.0 do relatório afirmava frequência de "~164 rebalanceamentos/ano" no In-Sample e uma narrativa de "IS mais turbulento que OOS"; o recálculo da análise crítica mostrou ~60/ano no IS e ~72/ano no OOS — número e narrativa corrigidos na v1.1. Exemplo concreto de por que nenhum número da IA entra no relatório sem contrapartida em arquivo de resultado congelado.
4. **Complexidade cortada contra a sugestão inicial (Fase 2.5).** O freio de volatilidade (target vol) chegou a ser considerado para a v1; a auditoria de complexidade o vetou (segundo mecanismo de risco + um parâmetro a mais no grid). Está documentado como pesquisa futura com protocolo próprio — não entrou pela porta dos fundos.
5. **Identidade duplicada detectada pela autoavaliação (Fase 5).** O HTML se intitulava "Estratégia Contrarian BTC/Caixa" enquanto o relatório usava CONTRAMARÉ; a autoavaliação apontou o ruído e a identidade foi unificada em todos os artefatos.
6. **O limite mais importante: o protocolo one-shot contra a tentação de re-tuning.** Após observar a derrota em Sharpe/Sortino no OOS, o caminho "natural" seria ampliar o grid (o ótimo caiu na borda `b3 = 2,00`) ou ajustar cortes. O regulamento proíbe, e a proibição foi cumprida: toda a análise pós-OOS (Seções 9–10 do relatório) usa exclusivamente as saídas congeladas, com regras comparativas fixadas a priori em `analise_resultados.py`.

## Como as saídas da IA eram validadas

Nenhuma saída da IA foi aceita por parecer correta. A validação seguiu três camadas:

1. **Programática:** scripts de verificação (auditoria T+1 dia a dia, igualdade de causalidade do Z-Score, reprodutibilidade por hash MD5, verificador de contraste/daltonismo da paleta) — a IA escreve o código E o teste que pode reprová-lo, e os testes abortam a execução em caso de violação.
2. **Numérica:** todo número citado em documento tem fonte em arquivo congelado (`resultados/metricas.json`, `resultados/analise_resultados.json`) gerado por código versionado — nunca em texto gerado.
3. **Humana:** decisões de arquitetura (tese, indicadores, convenções, o que cortar) foram da equipe; a IA executou, documentou e criticou.

## Compreensão do papel da IA na solução

A IA generativa funcionou como **multiplicador de rigor, não de complexidade**: o modelo final tem 4 parâmetros e duas fórmulas de uma linha — o que a IA adicionou não foi sofisticação de modelo, foi **camadas de auditoria** (red team pré-código, verificação dia a dia, autoavaliação adversarial) que uma equipe pequena não teria fôlego de produzir no prazo. O resultado característico desse arranjo é visível no produto final: um relatório em que os números mais desfavoráveis (IR −1,14 no OOS; o sinal de euforia vendendo cedo; o único ano perdendo do benchmark) foram calculados e publicados por iniciativa própria — porque a IA foi instruída a atacar o trabalho com a mesma régua da banca, antes da banca.
