# Kratos: From Sparta to Ragnarök

Apresentação em inglês sobre a história do Kratos, do primeiro God of War (2005) até Ragnarök e o epílogo Valhalla, com a cara do menu do jogo.

## Arquivos para usar (pasta `dist/`)

| Arquivo | Quando usar |
|---|---|
| `Kratos_Presentation.pdf` | PDF interativo. Os padrões verbais (gerúndio / infinitivo) aparecem sublinhados em cores. |
| `Kratos_Presentation_no-highlights.pdf` | O mesmo PDF sem os sublinhados de gramática. |
| `Kratos_Presentation_Interactive.html` | Versão com animações: brasas e neve caindo, títulos surgindo letra por letra, carimbos "DEFEATED", barras de status, mapa animado, cartas para tocar e revelar e a cutscene com o Odin (faixas de cinema, legendas digitadas e o Kratos grego aparecendo com um clarão vermelho). Funciona sem internet. |

### O que é interativo no PDF
- **Menu principal**: New Game, Chapter Select, Arsenal, Characters, Verb Patterns e Credits levam à página certa.
- **Chapter Select**: cada capa abre o capítulo.
- **Barra de rodapé** em todas as páginas: Back, Menu, Next e a linha da saga (Sparta → Valhalla), que leva a qualquer capítulo.
- **Verb Patterns**: cada exemplo tem um botão que volta para a página onde ele aparece.
- **Cutscene Kratos vs Odin** (página 10): a fala “Return my son… or you may meet the god I once was.”, com a resposta do Odin.
- Marcadores (sumário lateral) e transição em fade entre páginas, quando o leitor de PDF tem suporte (ex.: Adobe Acrobat em tela cheia).

> O formato PDF não roda animações. Para os efeitos animados, abra o `.html` no Safari ou no Chrome.

### Controles da versão HTML
- **→ / Espaço**: próxima página · **←**: página anterior · deslizar o dedo no iPad também funciona
- **↑ ↓ + Enter** no menu principal · **Esc** ou **M**: volta ao menu
- **F**: tela cheia · **G**: liga/desliga os destaques de gramática · **R**: revela as cartas "Plot twist" / "Secret"
- Na cutscene, o botão **Replay scene** repete a cena

## Páginas
1. Main menu · 2. Chapter select · 3. Prologue: The Ghost of Sparta · 4. God of War (2005) · 5. God of War II (2007) · 6. God of War III (2010) · 7. Interlude: A New Life in the North · 8. God of War (2018) · 9. God of War Ragnarök (2022) · 10. Cutscene: “The God I Once Was” (Kratos vs Odin) · 11. Epilogue: Valhalla (2023) · 12. The Arsenal · 13. Allies & Enemies · 14. Verb Patterns · 15. Credits

O texto usa de propósito os padrões verbais do *English File, Appendix p.164* (gerúndio, infinitivo com *to* e sem *to*). A página 14 junta todos os exemplos.

## Como gerar de novo

```bash
# 1. (opcional) refazer as imagens a partir das fontes originais
#    <pasta-de-envios> tem as imagens enviadas pelo autor: menu.jpg, gow3_close.png,
#    ascension.jpg, serpent.jpg, gow1_art.png e gow1_cover.jpg
python3 -I scripts/prep_images.py <pasta-com-os-repos-de-origem> <pasta-de-envios> assets/img
# 2. juntar fontes e imagens num HTML único
python3 -I scripts/build.py
# 3. gerar os PDFs (precisa do Playwright + Chromium)
node scripts/make_pdf.js dist/Kratos_Presentation_Interactive.html /tmp/raw.pdf
node scripts/make_pdf.js dist/Kratos_Presentation_Interactive.html /tmp/raw_clean.pdf clean
python3 -I scripts/finish_pdf.py /tmp/raw.pdf dist/Kratos_Presentation.pdf
python3 -I scripts/finish_pdf.py /tmp/raw_clean.pdf dist/Kratos_Presentation_no-highlights.pdf
# testes rápidos
node scripts/test_interaction.js dist/Kratos_Presentation_Interactive.html
node scripts/shots.js dist/Kratos_Presentation_Interactive.html <pasta-de-saida>
```

O código-fonte da apresentação está em `src/index.html`.

## Créditos
- **Jogos:** série God of War, de Santa Monica Studio / Sony Interactive Entertainment. Todas as imagens dos jogos pertencem aos donos e são usadas só neste trabalho escolar.
- **Origem das imagens:** artes e capturas oficiais tiradas de sites de fãs públicos no GitHub (`Samuel0422/Kratos`, `Gabiel001/god_of_war_3`, `CarlosAugustoPrado/God-of-War-Ragnarok`, `Eric081a/GodOfWar`), mais as imagens enviadas pelo autor (captura do menu, Kratos em God of War III, arte de Ascension, a Serpente do Mundo, arte e capa de God of War 2005). Na cutscene, o Kratos nórdico vem da captura do menu e o Odin vem da cena da visita de Odin e Thor, porque não deu para baixar a imagem exata dessa cena.
- **Fontes:** Cinzel, EB Garamond, Barlow Condensed e Noto Sans Runic (Google Fonts, SIL Open Font License).
