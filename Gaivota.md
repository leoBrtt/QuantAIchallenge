# AUTOAVALIAÇÃO HONESTA — PROJETO CONTRAMARÉ × MANUAL DE AVALIAÇÃO OFICIAL
### Desafio Quant AI 2026 (Itaú Asset) · escrita em 17/07/2026, com tempo hábil antes da entrega

Este documento responde, critério a critério, à pergunta: **"o trabalho, como está hoje, atende ao que a banca procura?"** — usando o Manual de Avaliação Oficial como régua, as saídas congeladas do motor como evidência, e uma análise adicional da série diária (`resultados/serie_backtest.csv`) feita especificamente para este documento. Nada aqui foi retocado: os números desfavoráveis estão reportados com o mesmo destaque que os favoráveis.

---

## Veredito geral (resposta direta)

**O núcleo técnico está a contento; o trabalho como entrega ainda não.** Os dois critérios de maior rigor (Modelagem 20% + Backtest 15% = 35% da nota) estão no nível que o Manual descreve como desempenho superior — replicável, transparente, com vieses mitigados e auditados. Porém, **~25% da nota está hoje descoberta**: não existe uma linha documentando o uso de IA Generativa (critério 4.7, peso 15%, uso **obrigatório**) nem uma conclusão formal com próximos passos (critério 4.6, peso 10%). E a Análise de Resultados (15%) está abaixo do seu potencial: o relatório é honesto, mas ainda majoritariamente descritivo — exatamente o ponto negativo que o Manual cita ("apresentação exclusivamente descritiva de métricas").

| # | Critério | Peso | Situação | Síntese |
|---|---|---:|:---:|---|
| 4.1 | Apresentação do robô | 5% | 🟡 | Nome CONTRAMARÉ existe e é coerente, mas a identidade não está unificada nos entregáveis |
| 4.2 | Conceito da estratégia | 20% | 🟡 | Hipótese clara e testável; originalidade moderada e o lado "vender na euforia" da tese é empiricamente frágil |
| 4.3 | Modelagem | 20% | 🟢 | Estruturada, replicável, 4 parâmetros; fragilidades conhecidas e mapeadas (inércia, whipsaw) |
| 4.4 | Backtest | 15% | 🟢 | O ponto mais forte do trabalho — 13 blindagens implementadas e auditadas dia a dia |
| 4.5 | Análise dos resultados | 15% | 🟡 | Honesta, porém rasa: falta atribuição, regimes, IR canônico — os números já existem (abaixo) |
| 4.6 | Conclusão e próximos passos | 10% | 🔴 | Não existe ainda |
| 4.7 | Uso de IA generativa | 15% | 🔴 | Uso intenso e real, mas **zero documentação** — o gap mais barato e mais urgente de fechar |

---

## 4.1 Apresentação do Robô (5%) — 🟡 parcial

**O que temos.** O nome **CONTRAMARÉ** (título do `RELATORIO_CONTRAMARE.md`) é coerente com a tese: operar contra a maré do sentimento — comprar no medo, vender na euforia. Passa no teste do Manual de "coerência entre o nome e a estratégia".

**Fragilidades honestas.**
- A identidade **não está unificada**: o HTML da Fase 4 se intitula "Estratégia Contrarian BTC/Caixa" (o nome CONTRAMARÉ não aparece em nenhum gráfico), o relatório usa CONTRAMARÉ, e este arquivo se chama `Gaivota.md` — se a equipe está considerando trocar o nome para "Gaivota", a decisão precisa ser tomada **agora** e propagada para todos os artefatos; identidade dupla na apresentação é exatamente o tipo de ruído que o critério penaliza ("baixa clareza na apresentação da proposta").
- Não existe um parágrafo de identidade conceitual ("quem é o robô, o que ele promete, o que ele não promete") abrindo o material de apresentação.

**O que fazer (esforço: baixo).** Decidir o nome definitivo; colocá-lo no título do `backtest_resultado.html`, no cabeçalho de todos os documentos e na abertura da apresentação, com uma frase de mandato: *"CONTRAMARÉ não promete vencer o Bitcoin em retorno — promete entregar uma fração controlada do risco dele."* Essa frase, além de identidade, prepara a banca para a leitura correta do OOS.

---

## 4.2 Conceito da Estratégia (20%) — 🟡 parcial

**O que temos.** Os três itens que o Manual exige explicitamente estão articulados (em `Explicação.md` e no relatório): o **fenômeno** (sobre-reação de preço e sentimento em cripto), a **justificativa** (comportamental: manada/euforia e pânico geram desvios temporários revertíveis) e a **forma de teste** (Z-Score móvel do score combinado → escala de exposição, IS/OOS com one-shot). A restrição `Peso_Mayer + Peso_FNG = 1` e os cortes simétricos mostram desenho anti-overfitting **no nível conceitual**, não só na implementação.

**Fragilidades honestas.**
- **Originalidade moderada:** Múltiplo de Mayer e Fear & Greed são indicadores de varejo amplamente conhecidos. O que é nosso é a combinação, a normalização por Z-Score móvel (que remove limiares arbitrários) e a escala de 7 níveis. A defesa deve assumir isso: simplicidade deliberada (princípio 2.3 do Manual), originalidade na **arquitetura de decisão**, não nos ingredientes.
- **O lado "vender na euforia" da tese é empiricamente frágil** — descoberta da análise desta autoavaliação: nas 44 vezes em que o robô foi a **−3 (zero BTC por euforia)**, o BTC subiu em média **+20,3% nos 90 dias seguintes** (mediana +11,5%). Ou seja, o sinal de venda historicamente vendeu **cedo demais** — momentum de alta domina o curto prazo em cripto. Já o lado "comprar no pânico" (+3) tem payoff positivo mas modesto (fwd 90d: média +6,4%, mediana +0,4% — poucos grandes acertos puxam a média). **A tese sobrevive como mandato de risco (cortar cauda esquerda), não como máquina de alpha** — e é assim que deve ser vendida à banca. Omitir isso e ser confrontado seria muito pior que declará-lo.

**O que fazer (esforço: baixo).** Reposicionar uma frase da tese nos documentos: o objetivo primário é **assimetria de drawdown com fração do risco**, e o custo esperado disso é abrir mão de upside em bull markets — o que o OOS confirmou. A tese ganha coerência retroativa com o resultado, sem retocar número algum.

---

## 4.3 Modelagem (20%) — 🟢 forte, com fragilidades mapeadas

**O que temos.** Todos os itens da rubrica: entradas definidas (BTC-USD + FNG, com datas e limitações declaradas), processamento descrito passo a passo (`Explicação.md` — cálculo e **motivo** de cada decisão), saída objetiva e testável (regra de rebalanceamento em 7 níveis, `w_BTC = (Escala+3)/6`), processo 100% sistemático e replicável (reprodutibilidade bit a bit verificada). Apenas 4 parâmetros livres, todos otimizados por protocolo declarado.

**Fragilidades honestas (a banca perspicaz vai achar — melhor que a gente ache primeiro).**
- **O robô é mais inerte do que a narrativa sugere:** passa **75,5% do tempo no nível 0 (50/50)**. Os níveis extremos somam ~10% do tempo (+3: 4,6%; −3: 5,5%). Com cortes em ±1,5σ/±1,75σ/±2,0σ, a "escala de 7 níveis" na prática opera como "50/50 com desvios ocasionais". Consequência: **grande parte do resultado vem da exposição estática média (~50%), não do timing** — ver item 4.5 para o teste que separa as duas coisas.
- **Whipsaw nos extremos:** 534 rebalanceamentos (~65/ano), dos quais **31% saltam ≥2 níveis num único dia** — os cortes são próximos entre si (0,25σ), então quando o Z-Score cruza a primeira banda, frequentemente atravessa várias. O custo dessa fricção é mensurável: **1,69 p.p./ano no IS e 2,04 p.p./ano no OOS** (diferença bruto→líquido). A frase do relatório "cortes largos reduzem churn e custo" (Seção 5) precisa ser **nuançada** — é verdadeira na comparação com cortes estreitos, mas 65 rebalanceios/ano não é pouco.
- **Dependência de índice de terceiro:** o FNG da Alternative.me não tem metodologia versionada publicamente — se o provedor mudou a receita ao longo do tempo, nossa série histórica mistura regimes do indicador. Mitigação existente: cache point-in-time. Declarar como limitação de dados.

**O que fazer (esforço: baixo).** Incluir a distribuição de tempo por nível e o diagnóstico de whipsaw no relatório (números acima, já calculados); corrigir a frase sobre churn; adicionar 1 parágrafo sobre a limitação do FNG.

---

## 4.4 Backtest (15%) — 🟢 o ponto mais forte do trabalho

**O que temos.** Cada item da rubrica do Manual tem contrapartida implementada e **auditada** (não apenas declarada): implementação própria (`backtest.py`, 500 linhas legíveis), coerência modelo↔simulação (o benchmark passa pelo mesmo motor), período justificado (máximo histórico disponível do FNG, warm-up excluído dos dois lados), e mitigação de vieses verificada dia a dia — T+1 exato, causalidade do Z-Score provada por igualdade IS ≡ full-sample, custos dentro do loop de otimização, protocolo one-shot cumprido (a Seção 7.2 do relatório reporta a derrota no OOS sem retoque — a melhor evidência de que o protocolo foi respeitado). Sem escolha oportunista de período: o início da janela é ditado pelos dados (primeiro Z-Score válido), não por conveniência.

**Fragilidades honestas.**
- **Custo de transação fixo em 10 bps, sem slippage/spread** — em cripto spot com ordens pequenas é razoável, mas não foi estressado.
- **Caixa a 0% a.a.** é conservador, porém irrealista no período OOS (T-bills pagaram 4–5% em 2023–2025). Sensibilidade já calculada: caixa a 3% adicionaria ~+1,5 p.p./ano à estratégia; a 5%, ~+2,5 p.p./ano (caixa médio de ~50%). Não muda a conclusão qualitativa do OOS (B&H ainda vence em retorno), e **por isso mesmo** é seguro e honesto reportar como estudo de sensibilidade — mantendo 0% como convenção-base.
- 2018–2022 ≈ 1,5 ciclo de BTC (já declarado).

**O que fazer (esforço: baixo, alto retorno).** Adicionar ao relatório uma mini-tabela de sensibilidade: custo 10/25/50 bps × caixa 0%/3%/5%, com parâmetros congelados (é análise pós-fato de robustez, não re-tuning — nenhum parâmetro é reescolhido).

---

## 4.5 Análise dos Resultados (15%) — 🟡 honesta, porém incompleta

**O que temos.** A Seção 7 do relatório é honesta (derrota no OOS reportada com destaque) e a leitura "a estratégia generalizou o comportamento; o regime não recompensou defesa" é correta e defensável — o beta (0,51) e a exposição (~50%) idênticos entre IS e OOS são a evidência de generalização.

**O que falta — e os números já existem** (calculados para esta autoavaliação; incorporar ao relatório):

**(a) Comportamento ao longo do tempo (ano a ano, líquido):**

| Ano | Estratégia | B&H | Leitura |
|---|---:|---:|---|
| 2018 | −31,6% | −59,6% | proteção em bear ✅ |
| 2019 | +37,9% | +92,4% | upside parcial (esperado) |
| 2020 | +93,4% | +303,5% | idem — não captura bolha |
| 2021 | +28,0% | +59,7% | idem |
| 2022 | −26,2% | −64,3% | proteção em bear ✅ (FTX: −2,8% vs −16,2%) |
| 2023 | +49,4% | +155,5% | custo da defesa em bull |
| 2024 | +59,3% | +121,1% | idem |
| 2025 | **−11,2%** | **−6,3%** | ⚠️ único ano em que perde MAIS que o B&H |
| 2026 YTD | −12,7% | −27,5% | proteção ✅ |

Isso responde diretamente aos itens "explicar o comportamento ao longo do tempo" e "identificar cenários favoráveis e desfavoráveis": a estratégia protege em **bears prolongados** (2018, 2022, 2026), protege menos em **crashes rápidos** (COVID: −38,6% vs −51,0% — o Z-Score de 90 dias é lento por construção) e tem seu **pior cenário relativo em mercados serrilhados** (2025: whipsaw comprou quedas que continuaram caindo e pagou custo dobrado).

**(b) Information Ratio canônico — obrigatório pela nossa própria régua** (`CLAUDE.md` §5: se reportar IR, calcular sobre retornos ativos): **IS −0,48 · OOS −1,13**. Em termos de retorno ativo contra o B&H, a estratégia **destrói valor de forma consistente** (~−18%/ano IS, ~−28%/ano OOS, tracking error 25–37%). Este é o número mais duro do projeto e **deve ser reportado por nós antes que a banca o calcule** — com a leitura correta: o mandato nunca foi retorno ativo, é perfil de risco (beta 0,5; DD −33,6% vs −53,1%; vol 26% vs 47%). Uma estratégia de exposição média 50% num ativo que só sobe **necessariamente** tem IR negativo; o que valida o desenho é a estabilidade do perfil, não o IR.

**(c) Atribuição: quanto é sinal, quanto é exposição média? — a análise que falta e que dá tempo de fazer.** Como o robô fica 75% do tempo em 50/50, a pergunta inevitável da banca é: *"e se vocês simplesmente segurassem 50% de BTC, sem sinal nenhum?"* Hoje não temos essa resposta. É um benchmark adicional barato: rodar o **mesmo motor com sinal constante 0** (carteira 50/50 com deriva, mesmíssima convenção T+1/custos) e reportar estratégia vs. base-estática vs. B&H. Se a estratégia bater a base estática em Sortino/drawdown, o **sinal** agrega; se não, a honestidade nos obriga a dizer que o valor está na dosagem (50%) e não no timing — e a conclusão do trabalho muda de ênfase. **Não é re-tuning** (nenhum parâmetro é reescolhido; é um comparativo com regra fixada a priori), mas deve ser declarado como análise pós-OOS.

**(d) Payoff dos extremos** (item 4.2 acima): entradas em −3 seguidas de +20% médio do BTC em 90d; entradas em +3 com mediana ~0. Reportar — é o tipo de autópsia de sinal que separa "análise crítica" de "descrição de métricas".

---

## 4.6 Conclusão e Próximos Passos (10%) — 🔴 lacuna

**O que temos.** Nada formalizado — o relatório termina em "Artefatos Gerados".

**O que fazer (esforço: médio).** Escrever a seção final com a maturidade que o Manual pede ("evitar conclusões desproporcionais às evidências"). Esqueleto sugerido, já coerente com os dados:

1. **O que ficou demonstrado:** o processo (não o retorno) — pipeline anti-viés auditado, parâmetros robustos na vizinhança, perfil de risco que generaliza para fora da amostra (beta/exposição/vol estáveis IS→OOS).
2. **O que NÃO ficou demonstrado:** geração de alpha vs. B&H (IR negativo nos dois períodos); eficácia do sinal de euforia isoladamente.
3. **Próximos passos realistas e honestos** (cada um com o protocolo que o tornaria legítimo):
   - **Redesenho do espaço de cortes a priori** (o ótimo caiu na borda b3=2,00) — com justificativa documentada ANTES de rodar e uma única nova rodada OOS;
   - **Histerese anti-whipsaw** (ex.: exigir 2 fechamentos consecutivos além do corte) — como pesquisa futura, pois adiciona parâmetro;
   - **Freio de volatilidade com `vol_alvo` fixado a priori** (já vetado da v1 pela auditoria; continua fora do grid);
   - **Caixa remunerado** (CDI/T-bill) como convenção da v2, com fonte de dados point-in-time;
   - **Assimetria de cortes** (evidência empírica: euforia ≠ pânico em payoff) — exigiria abandonar a simetria, dobrando parâmetros; só com protocolo novo.

---

## 4.7 Uso de IA Generativa (15%) — 🔴 lacuna crítica (e a mais barata de fechar)

**O problema.** O uso de IA é **obrigatório** e vale 15% — e o projeto, que usou IA generativa de forma intensa e genuinamente estrutural em TODAS as fases, não tem **uma linha** documentando isso. O Manual pune "uso superficial ou meramente declaratório"; nosso risco é o oposto e mais absurdo: uso profundo e **não declarado**.

**A matéria-prima já existe** (basta compilar, com artefatos como prova):
- **Fase 2 — pesquisa dirigida:** extração de boas práticas do Microsoft Qlib e PyPortfolioOpt com referências arquivo:linha (`ROADMAP.md`), incluindo a detecção de que o "Information Ratio" do Qlib é um Sharpe rf=0 e de que o N=238/252 deles não serve para um ativo 24/7;
- **Fase 2.5 — red team:** auditoria de estresse da arquitetura ANTES do código (warm-up, custos, guardas numéricas, protocolo anti-snooping — tudo registrado no `ROADMAP.md` com gravidade);
- **Fase 3 — implementação + auditoria independente:** motor gerado sob regulamento explícito (`CLAUDE.md` como contrato de comportamento da IA) e verificado por script de checagem dia a dia (Seção 4 do relatório);
- **Fase 4 — auditoria visual:** paleta validada por verificador programático de daltonismo/contraste, layout auditado por screenshot headless em iterações;
- **Esta autoavaliação** — a IA como avaliadora adversarial do próprio trabalho, produzindo os achados desfavoráveis das seções acima.

**O que fazer (esforço: baixo, retorno: 15% da nota).** Documento curto "USO_DE_IA.md" (ou seção do relatório final): para cada fase, o papel da IA, o artefato gerado, e — ponto que a banca valoriza — **onde a IA errou/foi corrigida ou teve limites impostos pela equipe** (ex.: a regra do `CLAUDE.md` §1 "proibido adivinhar pesos" existe precisamente para conter alucinação matemática da IA). Isso demonstra "compreensão do papel da IA na solução", o critério exato.

---

## Plano de ação para o tempo restante (priorizado por peso × esforço)

| Prioridade | Ação | Critério (peso) | Esforço |
|:---:|---|---|:---:|
| 1 | Escrever `USO_DE_IA.md` fase a fase, com artefatos e correções humanas | 4.7 (15%) | baixo |
| 2 | Incorporar ao relatório: tabela ano a ano, janelas de crise, IR canônico com leitura, distribuição por nível, payoff dos extremos | 4.5 (15%) | baixo (números prontos) |
| 3 | Rodar benchmark estático 50/50 (mesmo motor, sinal constante 0) e reportar atribuição sinal vs. exposição — declarado como análise pós-OOS | 4.5 (15%) | médio |
| 4 | Escrever Conclusão + Próximos Passos (esqueleto da seção 4.6 acima) | 4.6 (10%) | médio |
| 5 | Sensibilidade custo (10/25/50 bps) × caixa (0/3/5%) com parâmetros congelados | 4.4 (15%) | baixo |
| 6 | Unificar identidade do robô (CONTRAMARÉ ou Gaivota — decidir e propagar para HTML, relatório, capa) + frase de mandato | 4.1 (5%) | baixo |
| 7 | Ajustes de honestidade fina: nuançar "reduz churn", declarar limitação metodológica do FNG, reposicionar tese como mandato de risco | 4.2/4.3 | baixo |

**O que deliberadamente NÃO fazer, mesmo havendo tempo:** reotimizar parâmetros, ampliar o grid (o ótimo na borda fica como limitação declarada), trocar a função-objetivo, ou reexecutar o OOS com qualquer variação do sinal. O one-shot já foi consumido; qualquer uma dessas ações converteria nossa maior força (rigor de protocolo) na maior fraqueza (re-tuning disfarçado). Todas as ações do plano acima são **análise, documentação e benchmarks com regras fixadas** — nenhuma toca os parâmetros congelados.

---

*Fontes dos números deste documento: `resultados/metricas.json`, `resultados/serie_backtest.csv` e `resultados/grid_search_is.csv` (saídas congeladas de `backtest.py`); análises adicionais calculadas em 17/07/2026 sem alteração de parâmetros. Réguas: Manual de Avaliação Oficial (Criterios_Avaliacao_Desafio.pdf) e `CLAUDE.md` §1–§7.*
