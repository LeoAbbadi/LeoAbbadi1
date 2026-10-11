# Dados de produtos do TikTok Shop

A aba **Produtos em alta** mostra ranking por faturamento, tendência 24h, comissão e os
vídeos que mais venderam. Hoje ela vem com **dados de exemplo** (fictícios, marcados no
banco como `is_sample`) para o site funcionar em desenvolvimento.

## De onde tirar dados reais

Os concorrentes não coletam esses dados sozinhos: eles compram de provedores
especializados. No código do Kirva, por exemplo, aparecem integrações com FastMoss e
SociaVault.

| Opção | Como funciona | Observação |
|---|---|---|
| Provedor de dados (FastMoss, Kalodata, EchoTik e similares) | API paga com vendas, GMV, criadores e vídeos | Caminho mais rápido. Peça orçamento e confirme se a licença permite revender os dados no seu produto. |
| API oficial do TikTok Shop (Partner Center / Affiliate) | Dados de produtos e comissões de afiliado | Exige cadastro e aprovação como parceiro; não traz ranking de mercado inteiro. |
| Importação manual (CSV) | Você exporta de alguma ferramenta e sobe na área Admin | Bom para começar com poucos produtos selecionados à mão. |

**Não recomendo** montar um robô que copie dados do site do TikTok: viola os termos de uso
da plataforma e quebra a cada mudança no site.

## Importando CSV (já funciona)

Painel → Admin → envie um CSV com as colunas:

```
external_id, country, name, category, shop_name, image_url, product_url, price,
commission_pct, sales_1d, sales_7d, sales_30d, gmv_1d, gmv_7d, gmv_30d, creators_count
```

`country` é `BR` ou `US`. Aceita vírgula ou ponto e vírgula como separador e números no
formato brasileiro (`1.234,56`). A importação apaga os produtos de exemplo e atualiza os
que já existem pelo `external_id`.

## Ligando um provedor por API

Crie uma rotina diária (no próprio worker ou num cron da Railway) que:

1. Busca os produtos no provedor.
2. Converte cada item para as colunas acima.
3. Grava com o mesmo `INSERT ... ON CONFLICT` usado em `src/server/routes/products.ts`
   (`source` = nome do provedor).

O resto do site (ranking, filtros, tendências, favoritos) já funciona com esses dados.
