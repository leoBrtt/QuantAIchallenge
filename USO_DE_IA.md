# USO DE IA GENERATIVA NO PROCESSO (critério 4.7)

A IA generativa (Claude, Anthropic — Opus, via Claude Code) atuou como
co-piloto de pesquisa e engenharia em todo o projeto, sob as regras do
`CLAUDE.md`. Este documento registra **o que a IA fez, o que ela foi impedida
de fazer pelo protocolo, e onde ela discordou da equipe** — porque uso de IA
bem documentado inclui os atritos, não só os acertos.

## 1. O que a IA fez

- **Desenho do protocolo:** propôs e redigiu o `PRE_REGISTRO.md` e insistiu
  que ele fosse o **primeiro commit** do repositório, antes de qualquer
  execução — o hash `1191e77a` é a evidência auditável de que espaço de busca,
  objetivo e restrições precederam os resultados.
- **Pesquisa de dados:** identificou que, entre as fontes públicas de funding
  de perpétuos, apenas a BitMEX cobre todo o In-Sample (desde 2016; a Binance
  só tem histórico de set/2019 em diante) e verificou os dois extremos da
  série pela API antes de qualquer código de produção.
- **Gate de redundância:** antes de congelar o pré-registro, mediu as
  correlações do funding com FNG (0,45) e Mayer (0,43) no IS — critério
  pré-declarado de reprovação em 0,8 — e constatou que Mayer × FNG (0,77) são
  mais redundantes entre si do que qualquer um deles com o funding.
- **Engenharia com não-regressão:** implementou o motor de dois perfis e o
  validou ANTES da primeira execução do grid: 24 configurações reproduzidas
  exatamente contra um motor de referência de 2 indicadores com
  `peso_funding=0`; futuros +3 com funding zerado replica byte a byte o B&H
  spot; identidade `r_eq[t] = w_exec[t-1]·r_px[t]` verificada dia a dia.
- **Execução e reporte:** grids, OOS one-shot, análises pós-OOS, painéis
  Plotly e este conjunto de documentos.

## 2. O que o protocolo impediu a IA de fazer

- **Rodar o OOS mais de uma vez, ou ajustar qualquer coisa depois dele.** O
  resultado do perfil L/S (Sortino IS negativo; retorno OOS majoritariamente
  carrego de Selic) foi reportado como está, sem retoque.
- **Corrigir a interação restrição × mapeamento do L/S** (Relatório, Seção 7):
  descoberta *depois* da execução, teria sido trivial "consertar" relaxando a
  restrição e rodando de novo — o protocolo proíbe; virou limitação declarada
  e próximo passo.
- **Alargar o grid quando b3 = 3,0σ caiu na borda** (de novo): reportado como
  limitação, não corrigido.

## 3. Onde a IA discordou da equipe (e o registro disso)

- A equipe pediu que o histórico de iterações internas não fosse narrado no
  relatório. A IA concordou que um relatório não narra rascunhos — mas
  **recusou** redigir qualquer afirmação de que nenhuma informação pós-2022
  influenciou o desenho, por ser falsa. O acordo está na Seção 5 do
  Relatório: as afirmações verificáveis ("parâmetros escolhidos exclusivamente
  no IS"; "OOS executado uma única vez para este modelo") acompanhadas do
  caveat de **viés de desenho**, que vale para qualquer estratégia concebida
  em 2026.
- A IA recomendou limitar o perfil de futuros a |w| ≤ 1 (sem alavancagem),
  contra a ideia inicial de alavancagem: com a volatilidade do BTC, o drag de
  variância e o risco de ruína dominariam, e a complexidade não é pontuada
  pela banca. A equipe acatou.

## 4. Verificação humana

Todos os números do Relatório saem de artefatos regenerados por
`./atualizar.sh --offline` (determinístico a partir do cache congelado) e
podem ser conferidos contra `resultados/*.json`. O pipeline foi reexecutado
após o congelamento e reproduziu os resultados byte a byte.
