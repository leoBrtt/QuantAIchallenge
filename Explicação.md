# Explicação Técnica do Motor Quantitativo — Passo a Passo

Este documento explica, em linguagem direta, como o `backtest.py` vai funcionar do começo ao fim. Cada etapa traz o cálculo envolvido e **o motivo** de cada decisão de arquitetura. A ideia é que qualquer pessoa (inclusive a banca) consiga ler este arquivo e entender exatamente o que o programa faz e por que faz assim, sem precisar abrir o código.

O objetivo do programa é simples de enunciar: **decidir, dia a dia, quanto do patrimônio fica em Bitcoin e quanto fica em caixa**, usando dois indicadores objetivos (preço relativo à média e sentimento do mercado), e provar via backtest que essa regra teria performado bem — sem cair em nenhuma das armadilhas estatísticas que invalidariam o resultado.

---

## Visão Geral: as 6 etapas do programa

1. **Coletar e limpar os dados** (preço do BTC + índice de medo/ganância).
2. **Calcular os dois indicadores** (Múltiplo de Mayer + Fear & Greed normalizado).
3. **Combinar em um Score único e transformá-lo em Z-Score** (o "termômetro" da estratégia).
4. **Traduzir o Z-Score em uma alocação** (quanto por cento em BTC, numa escala de 7 níveis).
5. **Simular a carteira dia a dia** (com a regra T+1 e custos de transação).
6. **Otimizar os parâmetros e validar** (Grid Search no período de treino, teste único no período de validação).

Cada etapa abaixo detalha o cálculo e a justificativa.

---

## Conceitos-chave que aparecem o tempo todo

Antes das etapas, três conceitos que se repetem e que explicam a maior parte das decisões:

- **In-Sample (IS) vs. Out-of-Sample (OOS):** dividimos a história em dois. O período de **treino** (In-Sample, retornos até 31/12/2022) é onde temos permissão de ajustar/otimizar os parâmetros. O período de **teste** (Out-of-Sample, de 01/01/2023 em diante) fica "lacrado" — só olhamos para ele **uma vez**, no final, para ver se a estratégia funciona em dados que ela nunca "viu". Isso é o que separa uma estratégia real de uma que só decorou o passado.

- **Look-ahead bias (viés de antecipação):** o erro de usar, para tomar a decisão de hoje, uma informação que só estaria disponível no futuro. É o erro mais comum e mais fatal em backtests. Grande parte das regras abaixo existe só para garantir que isso nunca aconteça.

- **Overfitting (sobreajuste):** criar uma regra tão colada aos dados do passado que ela funciona lindamente no histórico e fracassa no futuro real. A defesa contra isso é ter poucos parâmetros, otimizá-los só no treino e testar uma única vez.

---

## ETAPA 1 — Coleta e limpeza dos dados

### O que o programa faz
Baixa duas séries temporais diárias:
- **Preço do Bitcoin** (BTC-USD, fechamento diário) via `yfinance`, começando em **2017-01-01**.
- **Crypto Fear & Greed Index** (FNG, um número de 0 a 100) via API da `Alternative.me`, que só existe a partir de **01/02/2018**.

Na primeira vez que baixa, salva os dados brutos em CSV local (cache). A partir daí, o backtest sempre lê do cache.

### Por que começar o preço em 2017 se a estratégia é de 2018 em diante?
Porque o Múltiplo de Mayer (Etapa 2) precisa de uma **média móvel de 200 dias**. Para ter um valor de média válido já no primeiro dia de 2018, precisamos de 200 dias de preço *antes* disso. Isso se chama **warm-up** (aquecimento): dados que existem só para "alimentar" os indicadores, mas que não entram na avaliação de performance.

### Por que cachear os dados brutos localmente?
Duas razões:
1. **Reprodutibilidade:** se rodarmos o backtest hoje e daqui a um mês, queremos o mesmo resultado. APIs podem revisar dados históricos silenciosamente (o Qlib chama isso de problema "point-in-time"). Congelar o CSV na primeira captura elimina esse risco.
2. **Honestidade:** garante que não estamos, sem querer, absorvendo ajustes retroativos nos preços que não existiam na época da decisão.

### Limpeza e verificação de sanidade (antes de qualquer cálculo)
O programa checa os dados brutos e **aborta com erro** se encontrar:
- Preço menor ou igual a zero (impossível, indica dado corrompido).
- Retorno diário com módulo acima de 60% (um salto assim quase sempre é erro de dado, não movimento real).
- Datas duplicadas ou fora de ordem.

Para dias em que o FNG está faltando, preenchemos com **forward-fill** (repete o último valor conhecido) — **nunca** para trás nem por interpolação.

### Por que forward-fill e nunca "para trás"?
Preencher um buraco de segunda-feira com o valor de terça-feira (`backfill`) ou interpolar entre os dois seria usar informação do futuro para decidir no passado — **look-ahead bias clássico**. O forward-fill só repete o que já era conhecido no momento, então é seguro.

---

## ETAPA 2 — Cálculo dos dois indicadores

### Indicador 1: Múltiplo de Mayer (valuation / "está caro ou barato?")

```
Mayer = Preço_de_Fechamento / SMA_200
```
onde `SMA_200` é a média simples dos últimos 200 preços de fechamento.

**Interpretação:** Mayer = 1 significa que o preço está exatamente na média de longo prazo. Mayer = 2 significa que o preço está o dobro da média (historicamente, muito caro / topo de euforia). Mayer = 0,5 significa metade da média (historicamente, muito barato / fundo de pânico).

**Por que este indicador?** É o termômetro de valuation mais simples e transparente que existe para o BTC — uma única divisão, sem parâmetros escondidos. Alinhado com o princípio de "Neutralidade de Complexidade" da banca: um modelo que qualquer pessoa entende em 10 segundos.

### Indicador 2: Fear & Greed normalizado (sentimento / "o mercado está com medo ou ganância?")

```
FNG_Norm = Valor_FNG / 50
```

**Interpretação:** o FNG bruto vai de 0 (medo extremo) a 100 (ganância extrema). Dividindo por 50, centramos em 1: `FNG_Norm = 1` é neutro, acima de 1 é ganância, abaixo de 1 é medo. Isso coloca os dois indicadores na **mesma escala** (ambos giram em torno de 1), o que permite combiná-los de forma justa na próxima etapa.

**Por que este indicador?** Captura algo que o preço sozinho não captura: a psicologia da multidão. E é um dado externo, objetivo, publicado por terceiros — não é algo que inventamos.

---

## ETAPA 3 — Score Combinado e Z-Score

### Passo 3a: combinar os dois indicadores em um número só

```
Score = (Mayer * Peso_Mayer) + (FNG_Norm * Peso_FNG)
```
com a restrição **`Peso_Mayer + Peso_FNG = 1`**.

**Por que forçar os pesos a somar 1?** Porque isso transforma dois parâmetros em **um só** (se `Peso_Mayer = 0,7`, então `Peso_FNG = 0,3` automaticamente). Menos parâmetros para otimizar = menos risco de overfitting e um espaço de busca menor no Grid Search. É uma decisão puramente anti-sobreajuste.

### Passo 3b: transformar o Score em Z-Score (o coração da estratégia)

O Score bruto não diz muita coisa sozinho — "Score = 1,3" é alto ou baixo? Depende do momento do mercado. Então medimos **quão longe o Score de hoje está da sua própria média recente**, em unidades de desvio-padrão:

```
Score_Z = (Score_hoje − média_móvel_90d(Score)) / desvio_padrão_móvel_90d(Score)
```

**Interpretação:** `Score_Z = +2` significa "o Score hoje está 2 desvios-padrão acima da sua média dos últimos 90 dias" — ou seja, mercado anormalmente caro/ganancioso em relação ao passado recente. `Score_Z = −2` é o oposto.

**Por que usar Z-Score em vez de cortes fixos no Score?** Esta é uma das decisões mais importantes do projeto. Se disséssemos "compre quando Mayer < 0,8", estaríamos **cravando um número arbitrário** que funcionou no passado — overfitting puro. O Z-Score, ao contrário, se **auto-ajusta**: ele não pergunta "o preço está abaixo de X?", ele pergunta "o preço está anormalmente baixo *em relação ao seu próprio comportamento recente*?". Isso remove a arbitrariedade e é robusto a mudanças de regime do mercado.

### As três blindagens do Z-Score (todas contra look-ahead bias)

1. **Janela causal (`.rolling(90, min_periods=90)`):** a média e o desvio de cada dia usam **apenas os 90 dias anteriores**, nunca dados futuros. O parâmetro `min_periods=90` garante que não calculamos um Z-Score com poucos dados no começo (que seria instável e sem sentido).

   > Por que isso importa: usar a média do período inteiro (`center=True` ou média do array completo) seria dizer "para decidir em 2019, usei a média que só ficou conhecida em 2025". Isso é o look-ahead bias mais sutil e mais comum — e invalidaria todo o backtest.

2. **Guarda de divisão por zero:** se o desvio-padrão móvel for praticamente zero (menor que 1e-8, o que acontece se o Score ficar "travado" num valor constante), **mantemos a escala do dia anterior** em vez de dividir por quase-zero (o que faria o Z-Score explodir para infinito e a alocação pular de um extremo ao outro por puro ruído).

3. **Não resetar na fronteira de 2023:** quando entramos no período de teste (jan/2023), o Z-Score continua usando os últimos 90 dias — que incluem out/nov/dez de 2022. **Isso é legítimo e não é leakage**, porque são dados do passado que estavam disponíveis na hora da decisão. Zerar o cálculo em 2023 por "excesso de zelo" só jogaria fora informação válida.

---

## ETAPA 4 — Do Z-Score para a alocação (a escala de 7 níveis)

### A escala
A estratégia nunca está "tudo ou nada". Ela opera em **7 níveis de exposição**: `{−3, −2, −1, 0, +1, +2, +3}`. A conversão de nível para percentual em BTC é linear:

```
w_BTC = (Escala + 3) / 6
```

| Escala | w_BTC (% em Bitcoin) | Resto em Caixa |
|:------:|:--------------------:|:--------------:|
|  +3    | 100%                 | 0%             |
|  +2    | 83,3%                | 16,7%          |
|  +1    | 66,7%                | 33,3%          |
|   0    | 50%                  | 50%            |
|  −1    | 33,3%                | 66,7%          |
|  −2    | 16,7%                | 83,3%          |
|  −3    | 0%                   | 100%           |

### Como o Z-Score define o nível: cortes simétricos e direção contrária
Definimos três "linhas de corte" simétricas: `±b1, ±b2, ±b3` (com `0 < b1 < b2 < b3`). O Z-Score é comparado a essas linhas para decidir o nível. A direção é **contrária (contrarian)**:

```
Score_Z >= +b3   ->  Escala −3  (mercado no auge: caro + ganancioso -> mínimo de BTC)
+b2 <= Score_Z < +b3  ->  Escala −2
+b1 <= Score_Z < +b2  ->  Escala −1
−b1 <  Score_Z < +b1  ->  Escala  0  (neutro: 50/50)
−b2 <  Score_Z <= −b1 ->  Escala +1
−b3 <  Score_Z <= −b2 ->  Escala +2
Score_Z <= −b3   ->  Escala +3  (mercado no fundo: barato + medo -> máximo de BTC)
```

**Por que contrária (contrarian)?** A tese da estratégia é comprar na baixa e vender na alta. Score alto = preço caro + euforia = hora de **reduzir** risco. Score baixo = preço barato + pânico = hora de **aumentar** exposição. Comprar quando todos estão com medo e vender quando todos estão gananciosos.

**Por que cortes simétricos (`±b`)?** Se deixássemos os 6 cortes totalmente livres, teríamos 6 parâmetros para otimizar — muito espaço para o Grid Search "garimpar" uma combinação sortuda (overfitting). Forçar simetria em torno de zero reduz de 6 para 3 parâmetros e ainda faz sentido econômico (tratamos euforia e pânico com a mesma régua).

**Por que a guarda de "manter a escala anterior" (ver Etapa 3) importa aqui:** sem ela, um Score_Z instável faria a escala saltar aleatoriamente entre níveis, gerando trades desnecessários que só queimam custo.

---

## ETAPA 5 — Simulação da carteira dia a dia

Aqui o programa "roda o filme" da estratégia. Duas regras dominam esta etapa: a **regra T+1** e os **custos de transação**.

### A regra T+1 (a blindagem central contra look-ahead bias)

O problema que ela resolve: se eu calculo o sinal com o preço de fechamento de hoje, eu **não posso** comprar/vender também no fechamento de hoje — porque no mundo real, quando o mercado fecha e eu vejo o preço, esse preço já passou. Preciso agir no dia seguinte.

A convenção exata do programa:

```
retorno_estratégia[t] = w_sinal[t−2] * r[t]
```
onde `r[t] = close[t] / close[t−1] − 1` é o retorno do dia `t`.

Lendo em português: **o sinal é calculado no fechamento do dia D; a ordem é executada no fechamento do dia D+1; e o peso novo só começa a capturar retorno a partir do dia D+2.** O custo da transação é debitado no dia da execução (D+1).

**Por que isso é inegociável?** Sem a defasagem, o backtest estaria "trapaceando": ganhando dinheiro com uma informação que, na vida real, chegaria tarde demais para ser usada. Uma banca de asset management detecta esse erro imediatamente e descarta o trabalho. A mesma defasagem é aplicada ao benchmark (Buy & Hold) para que a comparação seja justa.

### Custos de transação e controle de churn

Duas regras:
1. **Custo de 10 bps (0,10%)** sobre o valor negociado a cada rebalanceamento. Reportamos a curva de capital **com e sem** custos, para deixar transparente o impacto da fricção.
2. **Só rebalanceamos quando a escala muda de nível** — nunca fazemos ajustes diários para corrigir a "deriva" natural da carteira (quando o BTC sobe e desequilibra levemente os percentuais).

**Por que se preocupar tanto com custo?** Porque uma estratégia que rebalanceia todo dia pode parecer ótima no papel e perder dinheiro na prática, comida pelas taxas. É o **primeiro ataque** de qualquer avaliador sério. Além disso, o Z-Score pode ficar oscilando bem em cima de uma linha de corte, fazendo a escala vibrar entre dois níveis dia sim, dia não — o que geraria uma enxurrada de trades. Só rebalancear na mudança de nível controla isso.

### Como a curva de capital (equity) é construída
O patrimônio é sempre **marcado a mercado**:
```
patrimônio[t] = caixa[t] + quantidade_BTC[t] * preço[t]
```
recalculado a cada rebalanceamento. O caixa **não rende juros** (0% ao ano).

**Por que marcar a mercado em vez de encadear percentuais?** Encadear variações percentuais de preço isoladamente gera erros de composição quando a alocação muda no meio do caminho. Reconstruir o patrimônio a partir de "caixa + posição" a cada passo é a forma correta e à prova de erros.

**Por que caixa a 0%?** É a hipótese **conservadora** (não estamos inflando o resultado com um rendimento de renda fixa otimista) e evita ter que buscar mais uma fonte de dados (taxa de juros histórica). Se a estratégia ganha do Buy & Hold mesmo com o caixa rendendo zero, o resultado é ainda mais robusto.

---

## ETAPA 6 — Otimização (Grid Search) e validação

Esta é a etapa onde escolhemos os melhores valores dos 4 parâmetros livres — e onde mais nos protegemos contra a acusação de "vocês só decoraram o passado".

### Os 4 parâmetros a otimizar
1. `Peso_Mayer` (e `Peso_FNG = 1 − Peso_Mayer` sai de graça).
2, 3, 4. Os três cortes `b1 < b2 < b3`.

### Como o Grid Search funciona
O programa testa uma **grade** de combinações desses 4 parâmetros de forma determinística (força bruta organizada, sem chute). A grade é **grossa** de propósito: passos de ~0,25 desvio nos cortes e ~0,1 nos pesos, resultando em algumas centenas de combinações — não dezenas de milhares.

**Por que uma grade grossa em vez de fina?** Quanto mais combinações testamos, maior a chance de uma delas parecer ótima só por sorte (isso se chama **data snooping**). Uma grade grossa testa menos, encontra a região boa, e é honesta: não estamos vasculhando o espaço até achar o número mágico.

### A regra de ouro: otimizar SÓ no In-Sample
O Grid Search roda **exclusivamente sobre os dados de treino (até 2022)**. O período de teste (2023+) **não participa** da otimização de forma alguma.

### A função-objetivo pré-declarada
Antes de rodar qualquer coisa, declaramos qual métrica queremos maximizar: **o Sortino Ratio no In-Sample** (explicado na próxima seção). E cada combinação é avaliada **já com a regra T+1 e os custos dentro do loop**.

**Por que declarar a métrica antes?** Se rodássemos tudo e só depois escolhêssemos "ah, vou usar a métrica em que meu resultado ficou melhor", isso seria trapaça estatística. Fixar a métrica antes elimina essa tentação. E otimizar já com custos evita que uma configuração campeã "sem fricção" se revele perdedora quando a fricção entra.

### A trava anti-solução-degenerada
Impomos uma restrição: **a exposição média a BTC no treino tem que ser de pelo menos 25%**. Configurações que ficam quase sempre em caixa são descartadas.

**Por que essa trava?** Porque métricas de risco como Sortino e Calmar podem ser "enganadas" por uma estratégia que quase não opera: ela tem risco quase zero e retorno minúsculo, e a matemática pode ranqueá-la no topo. A trava impede que o otimizador conclua, absurdamente, que "a melhor estratégia é não fazer quase nada".

### O teste final: one-shot no Out-of-Sample
Depois que o Grid Search escolhe a melhor combinação **no treino**, congelamos esses parâmetros e rodamos **uma única vez** no período de teste (2023+). Se o resultado for ruim, **não voltamos** a mexer nos parâmetros — isso seria contaminar o teste.

**Por que uma única vez?** Porque o valor do período de teste está justamente em ele ser "virgem". Se ficarmos ajustando e re-testando, o período de teste deixa de ser teste e vira mais um período de treino disfarçado — e perdemos a única prova de que a estratégia funciona fora da amostra.

### Análise de robustez (o melhor argumento para a banca)
Geramos um **heatmap** da função-objetivo em torno do ponto ótimo. Se as combinações **vizinhas** ao ótimo performam de forma parecida (uma "superfície plana"), isso prova que os parâmetros são robustos — não achamos um pico isolado por sorte. Se o ótimo fosse um pico solitário cercado de resultados ruins, seria sinal de overfitting.

### Caveat de honestidade
Reconhecemos abertamente no relatório: o período 2018–2022 contém apenas ~1,5 ciclo completo do Bitcoin. São poucos ciclos independentes. Assumir isso explicitamente vale mais credibilidade do que fingir que 5 anos de dados diários equivalem a milhares de observações independentes.

---

## As métricas do relatório final (e por que cada uma)

Anualizamos tudo com **N = 365**, não 252.

> **Por que 365 e não 252?** O número 252 é o total de *pregões* de uma bolsa de ações por ano (fecha fim de semana e feriado). O Bitcoin negocia **24 horas, 7 dias por semana, 365 dias por ano**. Usar 252 subestimaria a anualização. Esse foi um ajuste explícito em cima das fórmulas do Qlib e do PyPortfolioOpt, que vêm calibradas para ações.

O retorno anualizado é sempre **geométrico**: `(1 + Retorno_Total)^(365/T) − 1`, usado de forma consistente em todas as métricas.

| Métrica | O que mede | Cálculo (resumido) |
|---|---|---|
| **Retorno anualizado** | Ganho médio por ano | `(1 + R_total)^(365/T) − 1` |
| **Volatilidade anualizada** | Quanto o resultado oscila | `desvio_padrão(retornos_diários) * sqrt(365)` |
| **Sharpe (rf=0)** | Retorno por unidade de risco total | `média(r) / desvio(r) * sqrt(365)` |
| **Sortino (MAR=0)** | Retorno por unidade de risco **de queda** | numerador igual ao Sharpe, mas o denominador só conta os dias negativos |
| **Calmar** | Retorno vs. pior tombo histórico | `retorno_anualizado / |Max_Drawdown|` |
| **Max Drawdown** | Maior queda do pico ao vale | `min(equity/pico_até_agora − 1)` |
| **Beta vs. Buy & Hold** (bônus) | Quanto a estratégia se move junto com o BTC | `covariância(estratégia, BTC) / variância(BTC)` |

### Detalhes que evitam erros nas métricas

- **Sharpe vs. "Information Ratio":** o Qlib chama `média/desvio * sqrt(N)` de "Information Ratio", mas isso é **tecnicamente um Sharpe com taxa livre de risco zero**. O Information Ratio de verdade se mede contra um benchmark. Renomeamos para **Sharpe (rf=0)** para não levar uma correção da banca por nomenclatura errada.

- **Sortino — por que penalizar só a queda?** A volatilidade "para cima" (dias de alta forte) não é um risco que o investidor queira evitar — pelo contrário. O Sortino corrige a injustiça do Sharpe (que penaliza alta e baixa igualmente) medindo o risco apenas com os retornos abaixo de zero (o MAR, Minimum Acceptable Return, que fixamos em 0).

- **Guardas de divisão por zero (importantes no Grid Search):**
  - Se o **desvio de queda for zero** (estratégia 100% em caixa num trecho, retornos todos iguais a zero), o Sortino daria infinito. Reportamos **N/A** — nunca substituímos por um número minúsculo (epsilon), que geraria um Sortino gigante e falso, ranqueando lixo no topo do Grid Search.
  - Se o **Max Drawdown for zero** (equity nunca caiu, ex.: sempre em caixa), o Calmar daria divisão por zero. Também reportamos **N/A**.
  - Configurações com métrica N/A são **descartadas** do Grid Search, não ranqueadas.

- **Proteção contra dado corrompido:** um retorno diário de −100% ou pior faria a fórmula do retorno acumulado (`cumprod`) chegar a zero ou negativo, e a potência fracionária do retorno anualizado retornaria um número inválido (NaN). Por isso a verificação de sanidade da Etapa 1 (|retorno| < 60%) roda **antes** de qualquer métrica. Num crash real de −90%, as fórmulas se comportam bem; o perigo é sempre dado sujo, não a matemática em si.

---

## Decisões que foram deliberadamente DEIXADAS DE FORA (e por quê)

Tão importante quanto o que o programa faz é o que ele **escolheu não fazer**, para respeitar o princípio de "Neutralidade de Complexidade" da banca:

- **Freio de Volatilidade (Target Volatility):** consideramos adicionar uma camada extra que reduziria a exposição automaticamente quando a volatilidade do mercado disparasse. **Cortado da versão 1.** Motivo: adicionaria um segundo mecanismo de risco por cima do Z-Score, tornando confuso saber "o que causou o resultado — o sinal ou o freio?", e criaria mais um parâmetro para otimizar (inflando o Grid Search que tanto trabalhamos para enxugar). Se um dia for usado, será com valor fixado de antemão, como estudo à parte, nunca dentro da otimização.

- **Deep Learning / Aprendizado por Reforço / caixas-pretas:** proibidos por princípio. A banca prefere um modelo simples, transparente e explicável (como este) a uma caixa-preta que ninguém consegue auditar.

- **Derivativos / alavancagem:** proibidos. Operamos apenas Bitcoin no mercado à vista (spot).

---

## Resumo de uma frase

O programa lê preço e sentimento do Bitcoin, mede o quão anormalmente "caro e ganancioso" (ou "barato e amedrontado") o mercado está em relação ao seu passado recente, e ajusta a fatia da carteira em BTC de acordo — comprando no medo e vendendo na euforia — tudo isso com defasagem de execução realista, custos de transação, parâmetros otimizados apenas no passado de treino e validados uma única vez num futuro que a estratégia nunca viu.
