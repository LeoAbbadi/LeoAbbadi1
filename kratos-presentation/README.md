# Kratos: From Sparta to Ragnarök

Apresentação em inglês sobre a história do Kratos, do primeiro God of War (2005) até Ragnarök e o epílogo Valhalla, com a cara do menu do jogo.

## Arquivos para usar (pasta `dist/`)

| Arquivo | Quando usar |
|---|---|
| `Kratos_Presentation.pdf` | PDF interativo. Os padrões verbais (gerúndio / infinitivo) aparecem sublinhados em cores. |
| `Kratos_Presentation_no-highlights.pdf` | O mesmo PDF sem os sublinhados de gramática. |
| `Kratos_Presentation_Interactive.html` | Versão com animações: brasas e neve caindo, títulos surgindo letra por letra, carimbos "DEFEATED", barras de status, mapa animado e cartas para tocar e revelar. Funciona sem internet. |

### O que é interativo no PDF
- **Menu principal**: New Game, Chapter Select, Arsenal, Characters, Verb Patterns e Credits levam à página certa.
- **Chapter Select**: cada capa abre o capítulo.
- **Barra de rodapé** em todas as páginas: Back, Menu, Next e a linha da saga (Sparta → Valhalla), que leva a qualquer capítulo.
- **Verb Patterns**: cada exemplo tem um botão que volta para a página onde ele aparece.
- Marcadores (sumário lateral) e transição em fade entre páginas, quando o leitor de PDF tem suporte (ex.: Adobe Acrobat em tela cheia).

> O formato PDF não roda animações. Para os efeitos animados, abra o `.html` no Safari ou no Chrome.

### Controles da versão HTML
- **→ / Espaço**: próxima página · **←**: página anterior · deslizar o dedo no iPad também funciona
- **↑ ↓ + Enter** no menu principal · **Esc** ou **M**: volta ao menu
- **F**: tela cheia · **G**: liga/desliga os destaques de gramática · **R**: revela as cartas "Plot twist" / "Secret"

## Páginas
1. Main menu · 2. Chapter select · 3. Prologue: The Ghost of Sparta · 4. God of War (2005) · 5. God of War II (2007) · 6. God of War III (2010) · 7. Interlude: A New Life in the North · 8. God of War (2018) · 9. God of War Ragnarök (2022) · 10. Epilogue: Valhalla (2023) · 11. The Arsenal · 12. Allies & Enemies · 13. Verb Patterns · 14. Credits

O texto usa de propósito os padrões verbais do *English File, Appendix p.164* (gerúndio, infinitivo com *to* e sem *to*). A página 13 junta todos os exemplos.

## Como gerar de novo

```bash
# 1. (opcional) refazer as imagens a partir das fontes originais
python3 -I scripts/prep_images.py <pasta-com-os-repos-de-origem> <screenshot-do-menu.jpg> assets/img
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
- **Origem das imagens:** artes e capturas oficiais tiradas de sites de fãs públicos no GitHub (`Samuel0422/Kratos`, `Gabiel001/god_of_war_3`, `CarlosAugustoPrado/God-of-War-Ragnarok`, `Eric081a/GodOfWar`), mais a captura do menu enviada pelo autor.
- **Fontes:** Cinzel, EB Garamond, Barlow Condensed e Noto Sans Runic (Google Fonts, SIL Open Font License).
