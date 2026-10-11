import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Pricing } from "../components/Pricing.tsx";
import { Coverflow } from "../components/Coverflow.tsx";
import { HeroScene, ProductArt } from "../components/Scene.tsx";
import { Counter, EASE, Reveal, SplitText, Tilt } from "../components/fx.tsx";
import { Icon } from "../components/Icons.tsx";
import { useScrollTo } from "../components/ui.tsx";
import { LABEL_INFO, planVideos } from "../../shared/combos.ts";

const FAQ = [
  ["Preciso saber editar vídeo?", "Não. Você grava os pedaços no celular, arrasta para as caixas de Gancho, Corpo e CTA e a ferramenta monta tudo. Cada vídeo sai pronto no formato vertical do TikTok."],
  ["O TikTok não vai achar que é conteúdo repetido?", "Cada vídeo sai com um selo que mostra o quanto ele é diferente dos anteriores e uma ordem de postagem que espalha os ganchos e corpos. Postando na ordem e variando a legenda dos marcados como Variação ou Parecido, sua página não fica repetitiva."],
  ["Onde meus vídeos ficam guardados?", "Os pedaços ficam no seu projeto para você gerar novos lotes quando quiser. Os vídeos prontos ficam disponíveis por 7 dias: baixe o ZIP com tudo e a planilha com a ordem de postagem."],
  ["De onde vêm os dados de produtos?", "De um provedor de dados de vendas do TikTok Shop, atualizado todo dia. O faturamento é uma estimativa feita a partir das vendas e do preço de cada produto."],
  ["Posso cancelar quando quiser?", "Pode. No mensal você cancela a qualquer momento pelo painel. E tem 7 dias de garantia: se não gostar, devolvemos 100% do valor."],
  ["Funciona no celular?", "Funciona no navegador do celular, do tablet e do computador. Para enviar muitos vídeos de uma vez, o computador é mais confortável."],
];

const TRENDING = [
  { name: "Escova secadora 3 em 1", cat: "Beleza", growth: "+184%", gmv: "R$ 412 mil", emoji: "💆‍♀️", theme: 1 },
  { name: "Legging cintura alta", cat: "Moda", growth: "+96%", gmv: "R$ 298 mil", emoji: "🩱", theme: 4 },
  { name: "Mini processador", cat: "Cozinha", growth: "+61%", gmv: "R$ 187 mil", emoji: "🥤", theme: 5 },
  { name: "Fone bluetooth ANC", cat: "Eletrônicos", growth: "+58%", gmv: "R$ 173 mil", emoji: "🎧", theme: 2 },
  { name: "Sérum vitamina C", cat: "Skincare", growth: "+44%", gmv: "R$ 151 mil", emoji: "🧴", theme: 0 },
  { name: "Garrafa térmica 1L", cat: "Casa", growth: "+39%", gmv: "R$ 120 mil", emoji: "🫗", theme: 3 },
];

// ---------------------------------------------------------------- topo

function Planner() {
  const [tab, setTab] = useState<"multi" | "prod" | "ia">("multi");
  const [h, setH] = useState(10);
  const [b, setB] = useState(5);
  const [c, setC] = useState(3);
  const [product, setProduct] = useState("");
  const navigate = useNavigate();
  const tabs = [
    { id: "multi", label: "Multiplicar", icon: <Icon.Layers size={20} /> },
    { id: "prod", label: "Produtos", icon: <Icon.Trend size={20} /> },
    { id: "ia", label: "Roteiro IA", icon: <Icon.Pen size={20} /> },
  ] as const;
  const step = (label: string, color: string, v: number, set: (n: number) => void, max: number) => (
    <div className="stepper">
      <span className="lbl">
        <span className="dot" style={{ color, background: color }} />
        {label}
      </span>
      <span className="ctrl">
        <button type="button" onClick={() => set(Math.max(1, v - 1))} aria-label={`Menos ${label}`}>−</button>
        <b>{v}</b>
        <button type="button" onClick={() => set(Math.min(max, v + 1))} aria-label={`Mais ${label}`}>+</button>
      </span>
    </div>
  );

  return (
    <motion.div
      className="glass strong planner"
      initial={{ opacity: 0, y: 40, scale: 0.96, filter: "blur(14px)" }}
      animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
      transition={{ duration: 1.1, delay: 0.5, ease: EASE }}
    >
      <h3 className="serif" style={{ fontSize: "2rem", fontWeight: 400 }}>Quantos vídeos?</h3>
      <div className="muted small">Calcule o que sai das suas gravações</div>
      <div className="tabs" role="tablist">
        {tabs.map((t) => (
          <button key={t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)} role="tab" aria-selected={tab === t.id}>
            {t.icon}
            {t.label}
            {tab === t.id && <motion.span layoutId="tab-line" className="tab-line" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, x: 16, filter: "blur(6px)" }}
          animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, x: -16, filter: "blur(6px)" }}
          transition={{ duration: 0.35, ease: EASE }}
        >
          {tab === "multi" && (
            <>
              {step("Ganchos", "#ffb877", h, setH, 10)}
              {step("Corpos", "#7cc4ff", b, setB, 10)}
              {step("CTAs", "#5ee6c3", c, setC, 5)}
              <div className="total">
                <span className="muted small">vídeos diferentes</span>
                <span className="n">
                  <Counter value={h * b * c} duration={0.6} />
                </span>
              </div>
              <Link to="/criar-conta" className="btn primary" style={{ width: "100%", justifyContent: "space-between" }}>
                Gerar meus vídeos <Icon.Arrow />
              </Link>
            </>
          )}
          {tab === "prod" && (
            <>
              {TRENDING.slice(0, 3).map((p, i) => (
                <div key={p.name} className="stepper">
                  <span className="lbl">
                    <span className="muted small" style={{ width: 14 }}>{i + 1}</span>
                    <span>
                      <div style={{ fontWeight: 600 }}>{p.name}</div>
                      <div className="faint small">{p.gmv} em 7 dias</div>
                    </span>
                  </span>
                  <span className="growth-up">{p.growth}</span>
                </div>
              ))}
              <p className="faint small" style={{ margin: "12px 0" }}>Exemplo ilustrativo. No painel, ranking atualizado todo dia.</p>
              <Link to="/criar-conta" className="btn primary" style={{ width: "100%", justifyContent: "space-between" }}>
                Ver ranking completo <Icon.Arrow />
              </Link>
            </>
          )}
          {tab === "ia" && (
            <form
              className="stack"
              style={{ gap: 14 }}
              onSubmit={(e) => {
                e.preventDefault();
                navigate(`/criar-conta?voltar=${encodeURIComponent(`/app/roteiros?produto=${product}`)}`);
              }}
            >
              <label className="field">
                Produto
                <input value={product} onChange={(e) => setProduct(e.target.value)} placeholder="Ex.: Escova secadora 3 em 1" />
              </label>
              <div className="muted small">Receba 10 ganchos, 5 corpos e 3 CTAs prontos para gravar, ou o roteiro inteiro da sua live.</div>
              <button className="btn primary" style={{ width: "100%", justifyContent: "space-between" }}>
                Gerar roteiro com IA <Icon.Arrow />
              </button>
            </form>
          )}
        </motion.div>
      </AnimatePresence>
    </motion.div>
  );
}

/** Trajeto pontilhado com o carrinho viajando (como o avião da referência). */
function FlightPath() {
  const reduce = useReducedMotion();
  const d = "M 790 790 C 830 720 860 650 900 600 S 980 520 1010 470";
  return (
    <svg className="flight" viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" aria-hidden>
      <motion.path d={d} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 2.4, delay: 0.8, ease: EASE }} />
      {!reduce && (
        <g>
          <circle r="16" fill="rgba(94,230,195,.18)">
            <animateMotion dur="7s" repeatCount="indefinite" path={d} rotate="auto" />
          </circle>
          <g>
            <animateMotion dur="7s" repeatCount="indefinite" path={d} rotate="auto" />
            <path d="M-7 -6 L9 0 L-7 6 L-3 0 Z" fill="#e9f4f2" />
          </g>
        </g>
      )}
      <g transform="translate(790 790)">
        <circle r="26" fill="rgba(94,230,195,.15)">
          <animate attributeName="r" values="18;30;18" dur="2.6s" repeatCount="indefinite" />
        </circle>
        <path d="M0 -26 C-12 -26 -18 -16 -18 -9 C-18 3 0 16 0 16 S18 3 18 -9 C18 -16 12 -26 0 -26 Z" fill="#5ee6c3" />
        <circle cy="-10" r="6" fill="#06231d" />
      </g>
    </svg>
  );
}

function ProductRail() {
  const scrollTo = useScrollTo();
  const rail = useRef<HTMLDivElement>(null);
  const scroll = (dir: number) => rail.current?.scrollBy({ left: dir * 420, behavior: "smooth" });
  return (
    <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1, delay: 1.1, ease: EASE }}>
      <div className="rail-head">
        <h3>Em alta no TikTok Shop</h3>
        <a href="#produtos" className="accent small" style={{ textDecoration: "none" }} onClick={(e) => { e.preventDefault(); scrollTo("produtos"); }}>Ver todos</a>
      </div>
      <div className="rail-wrap">
        <button className="btn icon rail-arrow l" onClick={() => scroll(-1)} aria-label="Voltar"><Icon.ArrowLeft /></button>
        <div className="rail" ref={rail}>
          {TRENDING.map((p, i) => (
            <motion.div
              key={p.name}
              className="pcard"
              initial={{ opacity: 0, y: 30, rotate: -2 }}
              animate={{ opacity: 1, y: 0, rotate: 0 }}
              transition={{ duration: 0.9, delay: 1.2 + i * 0.08, ease: EASE }}
              whileHover={{ y: -6 }}
            >
              <ProductArt theme={p.theme} emoji={p.emoji} seed={i} />
              <div className="meta">
                <strong>{p.name}</strong>
                <div className="row">
                  <span>{p.cat}</span>
                  <span className="growth-up">▲ {p.growth}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
        <button className="btn icon rail-arrow r" onClick={() => scroll(1)} aria-label="Avançar"><Icon.Arrow /></button>
      </div>
    </motion.div>
  );
}

function Hero() {
  const scrollTo = useScrollTo();
  return (
    <section className="hero">
      <div className="hero-scene"><HeroScene /></div>
      <div className="hero-shade" />
      <FlightPath />
      <div className="container hero-grid">
        <div>
          <motion.div className="eyebrow" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.8, delay: 0.2, ease: EASE }}>
            O TikTok Shop não espera
          </motion.div>
          <h1>
            <SplitText text="Grave uma vez." delay={0.3} />
            <br />
            <span className="hl"><SplitText text="Poste por meses." delay={0.55} /></span>
          </h1>
          <motion.div className="rule" initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ duration: 1, delay: 1, ease: EASE }} style={{ transformOrigin: "left" }} />
          <motion.p className="lead" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 1.05, ease: EASE }}>
            Grave 18 pedaços em 20 minutos e receba até 150 vídeos prontos, na ordem certa de postar. Descubra o que está
            vendendo e gere o roteiro com IA.
          </motion.p>
          <motion.div className="row" style={{ marginTop: 30, gap: 22 }} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 1.2, ease: EASE }}>
            <Link to="/criar-conta" className="btn primary big">
              Começar grátis <Icon.Arrow />
            </Link>
            <a href="#multiplicador" className="play" onClick={(e) => { e.preventDefault(); scrollTo("multiplicador"); }}>
              <span className="ring glass"><Icon.Play /></span>
              <span>
                <strong>Ver em ação</strong>
                <span>Como 18 vídeos viram 150</span>
              </span>
            </a>
          </motion.div>
        </div>
        <Planner />
      </div>
      <div className="container hero-bottom">
        <ProductRail />
        <motion.div
          className="glass features"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 1, delay: 1.3, ease: EASE }}
        >
          <div><Icon.Order /> Ordem certa de postar</div>
          <div><Icon.Calendar /> Calendário e legendas</div>
          <div><Icon.Wave /> Áudio padronizado</div>
          <div><Icon.Lock /> Pagamento seguro</div>
        </motion.div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- seções

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
      <span className="center serif" style={{ fontSize: "2.2rem", lineHeight: 1 }}>{value}</span>
    </label>
  );
  return (
    <div className="glass strong stack" style={{ gap: 26, padding: 32, borderRadius: 30 }}>
      <div className="calc">
        {field("Ganchos", h, setH, 10, "hook")}
        {field("Corpos", b, setB, 10, "body")}
        {field("CTAs", c, setC, 5, "cta")}
        <div className="result center">
          <div className="muted small">viram</div>
          <div className="big-number"><Counter value={total} duration={0.5} /></div>
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

const STEPS = [
  ["01", "Escolha o produto", "Veja o ranking do que está vendendo e gere o roteiro com IA: ganchos, corpos e CTAs prontos para gravar."],
  ["02", "Grave os pedaços", "Uns 20 minutos com o celular: por exemplo, 10 ganchos, 5 corpos e 3 CTAs, cada um num vídeo separado."],
  ["03", "Arraste para as caixas", "Solte cada vídeo na caixa de Gancho, Corpo ou CTA. A ferramenta padroniza formato, tamanho e volume."],
  ["04", "Baixe e poste", "Receba os vídeos com selo de originalidade, data sugerida e legenda. Tudo num ZIP só."],
];

export function Landing() {
  return (
    <main>
      <Hero />

      <section className="container" style={{ marginTop: 30 }}>
        <Reveal className="glass stats">
          <div><div className="v"><Counter value={150} /></div><div className="k">vídeos de 18 gravações</div></div>
          <div><div className="v"><Counter value={20} suffix=" min" /></div><div className="k">de gravação no celular</div></div>
          <div><div className="v"><Counter value={3} suffix=" min" /></div><div className="k">para montar tudo</div></div>
          <div><div className="v"><Counter value={7} suffix=" dias" /></div><div className="k">de garantia</div></div>
        </Reveal>
      </section>

      <section className="section" id="como-funciona">
        <div className="container">
          <Reveal className="section-head">
            <div className="eyebrow centered">Como funciona</div>
            <h2>Do celular para 150 vídeos <span className="hl">em quatro passos</span></h2>
            <p className="muted">Sem programa de edição, sem passar horas cortando vídeo.</p>
          </Reveal>
          <div className="grid cols-4">
            {STEPS.map(([n, t, d], i) => (
              <Reveal key={n} delay={i * 0.1}>
                <Tilt className="card hover" style={{ height: "100%" }}>
                  <div className="serif accent" style={{ fontSize: "3rem", lineHeight: 1, marginBottom: 14 }}>{n}</div>
                  <h3>{t}</h3>
                  <p className="muted small" style={{ margin: 0 }}>{d}</p>
                </Tilt>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="section" id="multiplicador" style={{ paddingTop: 40 }}>
        <Reveal className="section-head container">
          <div className="eyebrow centered">Multiplicador de vídeos</div>
          <h2>Cada combinação vira <span className="hl">um vídeo novo</span></h2>
        </Reveal>
        <Reveal>
          <Coverflow />
        </Reveal>
        <div className="container" style={{ marginTop: 60 }}>
          <Reveal>
            <Calculator />
          </Reveal>
          <div className="grid cols-3" style={{ marginTop: 20 }}>
            {(["original", "variacao", "parecido"] as const).map((l, i) => (
              <Reveal key={l} delay={i * 0.1} className="card">
                <span className={`pill ${l}`}>{LABEL_INFO[l].title}</span>
                <p className="muted small" style={{ margin: "12px 0 0" }}>{LABEL_INFO[l].tip}</p>
              </Reveal>
            ))}
          </div>
          <p className="center muted small" style={{ marginTop: 20 }}>
            A ordem de postagem coloca os ganchos novos primeiro e nunca repete o mesmo corpo em dois posts seguidos.
          </p>
        </div>
      </section>

      <section className="section" id="produtos">
        <div className="container grid cols-2" style={{ alignItems: "center", gap: 56 }}>
          <Reveal>
            <div className="eyebrow">Produtos em alta</div>
            <h2>Saiba o que vender <span className="hl">antes de gravar</span></h2>
            <p className="muted">
              Ranking por faturamento estimado em reais, tendências das últimas 24 horas, comissão de cada produto e os
              vídeos que mais venderam. Com dados do Brasil e dos EUA no plano Pro, para pegar a onda antes de ela chegar aqui.
            </p>
            <Link to="/criar-conta" className="btn primary">Ver produtos em alta <Icon.Arrow /></Link>
          </Reveal>
          <Reveal delay={0.15}>
            <Tilt className="card" max={5}>
              <table className="table">
                <thead><tr><th>Produto</th><th>7 dias</th><th>24h</th></tr></thead>
                <tbody>
                  {TRENDING.slice(0, 5).map((p, i) => (
                    <motion.tr key={p.name} initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: 0.2 + i * 0.08, ease: EASE, duration: 0.6 }}>
                      <td><span style={{ marginRight: 10 }}>{p.emoji}</span>{p.name}</td>
                      <td>{p.gmv}</td>
                      <td className="growth-up">{p.growth}</td>
                    </motion.tr>
                  ))}
                </tbody>
              </table>
              <p className="faint small" style={{ margin: "10px 0 0" }}>Ilustração com números de exemplo.</p>
            </Tilt>
          </Reveal>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 30 }}>
        <div className="container grid cols-2" style={{ alignItems: "center", gap: 56 }}>
          <Reveal className="card stack bob" style={{ gap: 14, padding: 30 }}>
            <div className="pill hot" style={{ alignSelf: "flex-start" }}><Icon.Spark size={14} /> Roteiro gerado com IA</div>
            {[
              ["Gancho · curiosidade", "“Ninguém me contou isso antes de eu comprar…”", "#ffd2ad"],
              ["Corpo · demonstração", "“Olha a diferença em 10 segundos…”", "#c3e3ff"],
              ["CTA", "“Toca no carrinho laranja antes que acabe.”", "#b7f6e4"],
            ].map(([k, v, color], i) => (
              <motion.div key={k} initial={{ opacity: 0, y: 12 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.3 + i * 0.25, duration: 0.6, ease: EASE }} className="glass dark" style={{ padding: 14, borderRadius: 16 }}>
                <div className="small" style={{ color, fontWeight: 600 }}>{k}</div>
                <div className="serif" style={{ fontSize: "1.35rem", lineHeight: 1.25 }}>{v}</div>
              </motion.div>
            ))}
            <div className="pill" style={{ alignSelf: "flex-start" }}>Roteiro de live · teleprompter · PDF</div>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="eyebrow">Roteiros com IA</div>
            <h2>Nunca mais trave <span className="hl">na frente da câmera</span></h2>
            <p className="muted">
              Digite o produto e receba 10 ganchos, 5 corpos e 3 CTAs pensados para o Multiplicador, cada gancho com uma
              técnica diferente. Para lives, o roteiro com o minuto de cada bloco, respostas para as dúvidas do chat e modo
              teleprompter.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 30 }}>
        <div className="container">
          <Reveal className="section-head">
            <h2>Tudo num lugar só</h2>
          </Reveal>
          <Reveal className="card table-wrap" style={{ padding: 10 }}>
            <table className="table compare">
              <thead><tr><th></th><th>Editar na mão</th><th>Facilitador</th></tr></thead>
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
                    <td>{typeof b === "string" ? <strong className="accent">{b}</strong> : <span className="yes">✓</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Reveal>
        </div>
      </section>

      <section className="section" id="planos" style={{ paddingTop: 30 }}>
        <div className="container">
          <Reveal className="section-head">
            <div className="eyebrow centered">Planos</div>
            <h2>Comece grátis. <span className="hl">Assine quando decolar.</span></h2>
          </Reveal>
          <Reveal><Pricing /></Reveal>
        </div>
      </section>

      <section className="section" id="faq" style={{ paddingTop: 30 }}>
        <div className="container" style={{ maxWidth: 800 }}>
          <Reveal className="section-head"><h2>Dúvidas frequentes</h2></Reveal>
          {FAQ.map(([q, a], i) => (
            <Reveal key={q} delay={i * 0.05} y={12}>
              <details className="faq">
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="container" style={{ paddingBottom: 60 }}>
        <Reveal className="glass strong cta-final">
          <div className="eyebrow centered" style={{ justifyContent: "center" }}>Seu próximo mês de conteúdo</div>
          <h2 style={{ maxWidth: 760, margin: "0 auto 18px" }}>Grave hoje. <span className="hl">Poste até o fim do mês.</span></h2>
          <p className="muted">20 vídeos grátis por mês, sem cartão.</p>
          <Link to="/criar-conta" className="btn primary big">Começar agora <Icon.Arrow /></Link>
        </Reveal>
      </section>
    </main>
  );
}

export function PricingPage() {
  return (
    <main className="section" style={{ paddingTop: 160 }}>
      <div className="container">
        <Reveal className="section-head">
          <div className="eyebrow centered">Planos</div>
          <h1 style={{ fontSize: "clamp(2.6rem, 6vw, 4.4rem)" }}>Comece grátis. <span className="hl">Assine quando decolar.</span></h1>
        </Reveal>
        <Reveal><Pricing /></Reveal>
      </div>
    </main>
  );
}
