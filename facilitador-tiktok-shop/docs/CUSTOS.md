# Custos, preço e margem

Todos os números saem de `scripts/custos.ts` (rode `npm run custos`). Troque os valores
lá quando os preços dos fornecedores ou o dólar mudarem. Premissa: US$ 1 = R$ 5,50.

## 1. Vídeos (Multiplicador)

Medido neste projeto com 18 pedaços (10 ganchos de 3 s, 5 corpos de 15 s, 3 CTAs de 5 s):

| Etapa | CPU |
|---|---|
| Padronizar os 18 pedaços (uma vez) | ~185 s |
| Juntar 150 vídeos (cópia, sem recodificar) | ~58 s |
| Montar o ZIP | ~20 s |
| **Total para 150 vídeos** | **~5 min de CPU, ~3 min de relógio** |

Preços de referência: CPU a US$ 0,028 por vCPU-hora (Railway), Cloudflare R2 a
US$ 0,015 por GB/mês e **download grátis**. Cada vídeo tem ~20 MB e fica guardado 7 dias.

**Resultado: ~R$ 0,0009 por vídeo, ou ~R$ 0,13 por lote de 150.**

> Use o **Cloudflare R2** e não o AWS S3: no S3 cada GB baixado custa ~US$ 0,09, e o
> download dos vídeos viraria o maior custo do produto (~R$ 1,50 por lote de 150).

## 2. Roteiros com IA (Claude)

| | Entrada | Saída (com raciocínio) | Custo |
|---|---|---|---|
| Roteiro de vídeos | ~700 tokens | ~3.500 tokens | |
| Roteiro de live (2 h) | ~800 tokens | ~8.000 tokens | |
| **Média com Claude Opus 5.5** (US$ 4 / US$ 20 por milhão) | | | **~R$ 0,55** |
| **Média com Claude Haiku 5.5** (US$ 0,10 / US$ 0,50 por milhão) | | | **~R$ 0,01** |

O código usa `claude-opus-5-5` por padrão (melhor qualidade de texto). Para reduzir o
custo de IA em ~40 vezes, troque `ANTHROPIC_MODEL=claude-haiku-5-5` no `.env`. Vale gerar
alguns roteiros com cada um e comparar antes de decidir.

## 3. Margem por cliente

Taxa de pagamento: Stripe com cartão nacional, ~3,99% + R$ 0,39 (confira a tabela atual).

**Cliente que usa a cota inteira (pior caso):**

| Plano | Receita/mês | Vídeos | IA Opus | IA Haiku | Taxa | Margem (Opus) | Margem (Haiku) |
|---|---|---|---|---|---|---|---|
| Grátis | R$ 0 | R$ 0,08 | R$ 1,10 | R$ 0,03 | – | −R$ 1,17 | −R$ 0,10 |
| Criador mensal (R$ 49) | R$ 49,00 | R$ 0,32 | R$ 8,24 | R$ 0,21 | R$ 2,35 | R$ 38 (78%) | R$ 46 (94%) |
| Pro mensal (R$ 89) | R$ 89,00 | R$ 1,39 | R$ 21,98 | R$ 0,55 | R$ 3,94 | R$ 62 (69%) | R$ 83 (93%) |
| Pro anual (R$ 597) | R$ 49,75 | R$ 1,39 | R$ 21,98 | R$ 0,55 | R$ 2,02 | R$ 24 (49%) | R$ 46 (92%) |

**Cliente típico (usa ~35% da cota):** margem de 79% a 89% com Opus e ~95% com Haiku.

O custo que pesa é a IA, não o vídeo. Por isso os roteiros têm cota por plano.

## 4. Custos fixos

| Item | Mês |
|---|---|
| Railway (site + worker + banco) | ~R$ 165 (US$ 30) |
| Cloudflare R2 (mínimo) | ~R$ 25 |
| Domínio | ~R$ 3 |
| **Total sem dados de produtos** | **~R$ 200** |
| Provedor de dados do TikTok Shop | sob orçamento (veja DADOS.md) |

**Ponto de equilíbrio:** ~5 assinantes do plano Criador pagam a infraestrutura. Com um
provedor de dados de R$ 2.000/mês, são ~35 assinantes Pro.

## 5. Por que esses preços

- Concorrentes vistos: GeraViral (R$ 59/mês ou R$ 197/ano) e Kirva (R$ 97/mês ou R$ 597/ano).
- O **Criador a R$ 49** entra abaixo dos dois para quem só quer o Multiplicador.
- O **Pro a R$ 89** fica entre os dois, com mais vídeos e dados dos EUA.
- O **anual a R$ 597** iguala o Kirva e garante o caixa do ano. Se quiser competir com o
  anual de R$ 197 do GeraViral, use Haiku nos roteiros para manter a margem.
- O maior custo real vai ser **aquisição de clientes** (anúncios e afiliados), não a nuvem.
