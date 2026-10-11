# Testar de graça, gerando vídeos de verdade

Use o **GitHub Codespaces**: um computador na nuvem que o GitHub empresta de graça
(60 horas por mês na máquina de 2 núcleos, sem cartão). O site, o banco e o FFmpeg
ligam sozinhos lá dentro, e você abre o site no navegador, inclusive no celular.

## Passo a passo

1. Abra este link logado na sua conta do GitHub:
   **https://codespaces.new/LeoAbbadi/LeoAbbadi1?ref=claude/video-editing-ai-platform-u0fifg**
2. Clique em **Create codespace**. A primeira vez demora uns 5 minutos (instala tudo).
3. Quando aparecer no terminal **"Facilitador ligado"**, abra a aba **Portas (Ports)**
   e clique no ícone de globo da porta **3000**. O site abre numa aba nova.
4. Entre com a conta de teste **demo@facilitador.local / demo12345** (já é plano Pro)
   ou crie a sua. Em **Planos**, o botão de assinar ativa o plano **sem cobrar nada**.
5. Crie um projeto no **Multiplicador**, envie seus vídeos e gere. Os vídeos saem
   montados de verdade, com botão de baixar e o ZIP com todos.

## Para não gastar a cota grátis

- O Codespace desliga sozinho depois de 30 minutos parado. Para usar de novo, abra
  github.com/codespaces e clique nele: em 1 minuto o site volta.
- Cada hora ligado gasta 2 das 120 horas-núcleo grátis do mês (ou seja, 60 horas).
- O espaço grátis é de 15 GB por mês. Um lote de 150 vídeos ocupa ~2 a 3 GB e é apagado
  sozinho depois de 2 dias. Para testar, prefira lotes menores (20 a 50 vídeos).
- Quando terminar os testes, apague o Codespace em github.com/codespaces
  (os arquivos do projeto continuam salvos no GitHub).
- Se a cota acabar, o GitHub só para o Codespace; não cobra nada sem você colocar um
  limite de gastos.

## Dúvidas comuns

- **A página não abre:** confira se o terminal mostra "Facilitador ligado". Se o
  terminal foi fechado, abra um novo e rode `bash .devcontainer/start.sh`.
- **Roteiros com IA:** sem chave da Anthropic, saem roteiros de exemplo. Para testar a
  IA de verdade, coloque `ANTHROPIC_API_KEY=...` no arquivo
  `facilitador-tiktok-shop/.env` e reinicie (Ctrl+C no terminal e `bash .devcontainer/start.sh`).
- **Mostrar para outra pessoa:** na aba Portas, clique com o botão direito na porta 3000
  → Port Visibility → Public. Qualquer um com o link consegue abrir enquanto o Codespace estiver ligado.
