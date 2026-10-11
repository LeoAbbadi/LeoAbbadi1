import { useState } from "react";
import { Link } from "react-router";
import { Pricing } from "../components/Pricing.tsx";
import { LABEL_INFO, planVideos } from "../../shared/combos.ts";

const FAQ = [
  [
    "Preciso saber editar vídeo?",
    "Não. Você grava os pedaços no celular, arrasta para as caixas de Gancho, Corpo e CTA e a ferramenta monta tudo. Cada vídeo sai pronto no formato vertical do TikTok.",
  ],
  [
    "O TikTok não vai achar que é conteúdo repetido?",
    "Cada vídeo sai com um selo que mostra o quanto ele é diferente dos anteriores e uma ordem de postagem que espalha os ganchos e corpos. Postando na ordem e variando a legenda dos marcados como Variação ou Parecido, sua página não fica repetitiva.",
  ],
  [
    "Onde meus vídeos ficam guardados?",
    "Os pedaços ficam guardados no seu projeto para você gerar novos lotes quando quiser. Os vídeos prontos ficam disponíveis para baixar por 7 dias. Baixe o ZIP com tudo e a planilha com a ordem de postagem.",
  ],
  [
    "De onde vêm os dados de produtos?",
    "De um provedor de dados de vendas do TikTok Shop, atualizado todo dia. O faturamento é uma estimativa feita a partir das vendas e do preço de cada produto.",
  ],
  [
    "Posso cancelar quando quiser?",
    "Pode. No mensal você cancela a qualquer momento pelo painel. E tem 7 dias de garantia: se não gostar, devolvemos 100% do valor.",
  ],
  [
    "Funciona no celular?",
    "Funciona no navegador do celular, do tablet e do computador. Para enviar muitos vídeos de uma vez, o computador é mais confortável.",
  ],
];

function Calculator() {
  const [h, setH] = useState(10);
  const [b, setB] = useState(5);
  const [c, setC] = useState(3);
  const total = h * b * c;
  const plan = planVideos(
    Array.from({ length: h }, (_, i) => `g${i}`),
    Array.from({ length: b }, (_, i) => `c${i}`),
    Array.from({ length: c }, (_, i) => `t${i}`),
    total,
  );
  const count = (l: string) => plan.filter((v) => v.label === l).length;
  const field = (label: string, value: number, set: (n: number) => void, max: number, cls: string) => (
    <label className="field">
      <span className={`slot-chip ${cls}`}>{label}</span>
      <input type="range" min={1} max={max} value={value} onChange={(e) => set(Number(e.target.value))} />
      <span className="center" style={{ fontSize: "1.6rem", fontWeight: 800 }}>{value}</span>
    </label>
  );
  return (
    <div className="card pad-lg stack" style={{ gap: 24 }}>
      <div className="calc">
        {field("Ganchos", h, setH, 10, "hook")}
        {field("Corpos", b, setB, 10, "body")}
        {field("CTAs", c, setC, 5, "cta")}
        <div className="result center">
          <div className="muted small">viram</div>
          <div className="big-number hl">{total}</div>
          <div className="muted small">vídeos diferentes</div>
        </div>
      </div>
      <div className="row" style={{ justifyContent: "center" }}>
        <span className="pill original">{count("original")} Originais</span>
        <span className="pill variacao">{count("variacao")} Variações</span>
        <span className="pill parecido">{count("parecido")} Parecidos</span>
        <span className="muted small">gravando só {h + b + c} pedaços</span>
      </div>
    </div>
  );
}

export function Landing() {
  return (
    <main>
      <section className="hero">
        <div className="container hero-grid">
          <div>
            <div className="eyebrow">● Para criadores e afiliados do TikTok Shop</div>
            <h1>
              Grave uma vez.
              <br />
              <span className="hl">Poste por meses.</span>
            </h1>
            <p className="lead">
              Grave 18 pedaços em 20 minutos e receba até 150 vídeos prontos, na ordem certa de postar. Descubra os
              produtos que estão vendendo agora e gere o roteiro com IA.
            </p>
            <div className="row" style={{ marginTop: 28 }}>
              <Link to="/criar-conta" className="btn primary big">
                Testar grátis
              </Link>
              <a href="#como-funciona" className="btn ghost big">
                Ver como funciona
              </a>
            </div>
            <p className="faint small" style={{ marginTop: 14 }}>
              Sem cartão para testar · 20 vídeos grátis por mês
            </p>
          </div>
          <div className="phone-stack" aria-hidden>
            {[
              ["Gancho 3", "Corpo 1", "CTA 2"],
              ["Gancho 7", "Corpo 4", "CTA 1"],
              ["Gancho 1", "Corpo 2", "CTA 3"],
            ].map((parts, i) => (
              <div className="phone" key={i}>
                <div className="seg" style={{ top: 10, background: "#ff6a3d33", color: "#ffb79e" }}>{parts[0]}</div>
                <div className="seg" style={{ top: "38%", background: "#6aa8ff33", color: "#b7d3ff" }}>{parts[1]}</div>
                <div className="seg" style={{ bottom: 10, background: "#2ee6a633", color: "#a5f5d7" }}>{parts[2]}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section alt" id="como-funciona">
        <div className="container">
          <div className="section-head">
            <h2>Do celular para 150 vídeos em 4 passos</h2>
            <p className="muted">Sem programa de edição, sem passar horas cortando vídeo.</p>
          </div>
          <div className="grid cols-4">
            {[
              ["1", "Escolha o produto", "Veja o ranking do que está vendendo e gere o roteiro com IA: ganchos, corpos e CTAs prontos para gravar."],
              ["2", "Grave os pedaços", "Uns 20 minutos com o celular: por exemplo, 10 ganchos, 5 corpos e 3 CTAs, cada um num vídeo separado."],
              ["3", "Arraste para as caixas", "Solte cada vídeo na caixa de Gancho, Corpo ou CTA. A ferramenta padroniza formato, tamanho e volume."],
              ["4", "Baixe e poste", "Receba os vídeos com selo de originalidade, data sugerida e legenda. Baixe tudo num ZIP só."],
            ].map(([n, t, d]) => (
              <div className="card" key={n}>
                <div className="pill hot" style={{ marginBottom: 12 }}>Passo {n}</div>
                <h3>{t}</h3>
                <p className="muted small" style={{ margin: 0 }}>{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="multiplicador">
        <div className="container">
          <div className="section-head">
            <div className="eyebrow">Multiplicador de vídeos</div>
            <h2>Cada combinação vira um vídeo novo</h2>
            <p className="muted">Mexa nos números e veja quantos vídeos saem dos seus pedaços.</p>
          </div>
          <Calculator />
          <div className="grid cols-3" style={{ marginTop: 24 }}>
            {(["original", "variacao", "parecido"] as const).map((l) => (
              <div className="card" key={l}>
                <span className={`pill ${l}`}>{LABEL_INFO[l].title}</span>
                <p className="muted small" style={{ margin: "10px 0 0" }}>{LABEL_INFO[l].tip}</p>
              </div>
            ))}
          </div>
          <p className="center muted small" style={{ marginTop: 18 }}>
            A ordem de postagem coloca os ganchos novos primeiro e nunca repete o mesmo corpo em dois posts seguidos.
          </p>
        </div>
      </section>

      <section className="section alt" id="produtos">
        <div className="container grid cols-2" style={{ alignItems: "center", gap: 40 }}>
          <div>
            <div className="eyebrow">Produtos em alta</div>
            <h2>Saiba o que vender antes de gravar</h2>
            <p className="muted">
              Ranking por faturamento estimado em reais, tendências das últimas 24 horas, comissão de cada produto e os
              vídeos que mais venderam. Com dados do Brasil e dos EUA no plano Pro, para pegar a onda antes de chegar aqui.
            </p>
            <Link to="/criar-conta" className="btn primary">
              Ver produtos em alta
            </Link>
          </div>
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>7 dias</th>
                  <th>24h</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["Escova secadora 3 em 1", "R$ 412 mil", "+184%"],
                  ["Legging cintura alta", "R$ 298 mil", "+96%"],
                  ["Mini processador elétrico", "R$ 187 mil", "+61%"],
                  ["Organizador de geladeira", "R$ 143 mil", "+38%"],
                ].map(([n, g, d]) => (
                  <tr key={n}>
                    <td>{n}</td>
                    <td>{g}</td>
                    <td className="growth-up">{d}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="faint small" style={{ margin: "10px 0 0" }}>Ilustração com números de exemplo.</p>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container grid cols-2" style={{ alignItems: "center", gap: 40 }}>
          <div className="card stack">
            <div className="pill hot">Roteiro de vídeo</div>
            <div className="small"><strong>Gancho (curiosidade):</strong> "Ninguém me contou isso antes de eu comprar..."</div>
            <div className="small"><strong>Corpo (demonstração):</strong> "Olha a diferença em 10 segundos..."</div>
            <div className="small"><strong>CTA:</strong> "Toca no carrinho laranja antes que acabe."</div>
            <div className="pill" style={{ marginTop: 8 }}>Roteiro de live · teleprompter · PDF</div>
          </div>
          <div>
            <div className="eyebrow">Roteiros com IA</div>
            <h2>Nunca mais trave na frente da câmera</h2>
            <p className="muted">
              Digite o produto e receba 10 ganchos, 5 corpos e 3 CTAs pensados para o Multiplicador, já com técnicas
              diferentes. Para lives, um roteiro com o minuto de cada bloco, respostas para as dúvidas do chat e modo
              teleprompter.
            </p>
          </div>
        </div>
      </section>

      <section className="section alt">
        <div className="container">
          <div className="section-head">
            <h2>Tudo num lugar só</h2>
          </div>
          <div className="card table-wrap">
            <table className="table compare">
              <thead>
                <tr>
                  <th></th>
                  <th>Editar na mão</th>
                  <th>Facilitador</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["150 vídeos a partir de 18 gravações", "dias de edição", "minutos"],
                  ["Ordem de postagem com selo de originalidade", false, true],
                  ["Calendário e legendas prontas", false, true],
                  ["Áudio com volume padronizado entre os pedaços", false, true],
                  ["Ranking de produtos por faturamento", false, true],
                  ["Roteiros de vídeo e de live com IA", false, true],
                  ["ZIP com tudo + planilha de postagem", false, true],
                ].map(([k, a, b]) => (
                  <tr key={String(k)}>
                    <td>{k}</td>
                    <td>{typeof a === "string" ? <span className="muted">{a}</span> : <span className="no">—</span>}</td>
                    <td>{typeof b === "string" ? <strong className="mint">{b}</strong> : <span className="yes">✓</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="section" id="planos">
        <div className="container">
          <div className="section-head">
            <h2>Planos</h2>
            <p className="muted">Comece grátis. Assine quando estiver postando todo dia.</p>
          </div>
          <Pricing />
        </div>
      </section>

      <section className="section alt" id="faq">
        <div className="container" style={{ maxWidth: 760 }}>
          <div className="section-head">
            <h2>Dúvidas frequentes</h2>
          </div>
          {FAQ.map(([q, a]) => (
            <details className="faq" key={q}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
          <div className="center" style={{ marginTop: 40 }}>
            <Link to="/criar-conta" className="btn primary big">
              Começar agora
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}

export function PricingPage() {
  return (
    <main className="section">
      <div className="container">
        <div className="section-head">
          <h1 style={{ fontSize: "2.4rem" }}>Planos</h1>
          <p className="muted">Comece grátis. Assine quando estiver postando todo dia.</p>
        </div>
        <Pricing />
      </div>
    </main>
  );
}
