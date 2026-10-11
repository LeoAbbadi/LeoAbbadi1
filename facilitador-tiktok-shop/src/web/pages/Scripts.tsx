import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { api, DEMO, type LiveScript, type ScriptDetail, type ScriptSummary, type VideoScript } from "../api.ts";
import { CopyButton, ErrorBox, Loading, PageHead, useLoad } from "../components/ui.tsx";
import { useSession } from "../session.tsx";
import { date } from "../format.ts";

export function ScriptsPage() {
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const history = useLoad(() => api<ScriptSummary[]>("/api/scripts"), []);
  const [kind, setKind] = useState<"videos" | "live">("videos");
  const [productName, setProductName] = useState(params.get("produto") ?? "");
  const [details, setDetails] = useState("");
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("animado");
  const [liveMinutes, setLiveMinutes] = useState(120);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const left = me ? me.limits.scriptsPerMonth - me.usage.scripts : 0;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api<{ id: string }>("/api/scripts", { body: { kind, productName, details, audience, tone, liveMinutes } });
      await refresh();
      navigate(`/app/roteiros/${s.id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead title="Roteiros com IA" sub={`Você ainda tem ${Math.max(0, left)} roteiros este mês.`} />
      <form className="card pad-lg stack" onSubmit={submit} style={{ gap: 16 }}>
        <div className="toggle" style={{ alignSelf: "flex-start" }}>
          <button type="button" className={kind === "videos" ? "on" : ""} onClick={() => setKind("videos")}>
            Vídeos (para o Multiplicador)
          </button>
          <button type="button" className={kind === "live" ? "on" : ""} onClick={() => setKind("live")}>
            Live
          </button>
        </div>
        <div className="grid cols-2">
          <label className="field">
            Produto
            <input value={productName} onChange={(e) => setProductName(e.target.value)} required placeholder="Ex.: Escova secadora 3 em 1" />
          </label>
          <label className="field">
            Público
            <input value={audience} onChange={(e) => setAudience(e.target.value)} placeholder="Ex.: mulheres 25-40 que treinam em casa" />
          </label>
        </div>
        <label className="field">
          Sobre o produto
          <textarea
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            placeholder="Preço, diferenciais, para que serve, o que vem na caixa. Quanto mais real, melhor o roteiro."
          />
        </label>
        <div className="grid cols-2">
          <label className="field">
            Tom
            <select value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="animado">Animado</option>
              <option value="direto">Direto</option>
              <option value="engracado">Engraçado</option>
              <option value="confiavel">Confiável</option>
            </select>
          </label>
          {kind === "live" && (
            <label className="field">
              Duração da live
              <select value={liveMinutes} onChange={(e) => setLiveMinutes(Number(e.target.value))}>
                {[30, 60, 90, 120, 180].map((m) => (
                  <option key={m} value={m}>
                    {m >= 60 ? `${m / 60}h${m % 60 ? "30" : ""}` : `${m} min`}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        <ErrorBox error={error} />
        <div className="row">
          <button className="btn primary" disabled={busy || left <= 0}>
            {busy ? "Escrevendo o roteiro... (até 1 minuto)" : "Gerar roteiro"}
          </button>
          {left <= 0 && (
            <span className="small muted">
              Roteiros do mês esgotados. <Link to="/planos">Ver planos</Link>
            </span>
          )}
        </div>
      </form>

      <div className="card" style={{ marginTop: 24 }}>
        <h3>Seus roteiros</h3>
        {history.loading ? (
          <Loading />
        ) : history.data?.length ? (
          <table className="table">
            <tbody>
              {history.data.map((s) => (
                <tr key={s.id} className="clickable" onClick={() => navigate(`/app/roteiros/${s.id}`)}>
                  <td>{s.product_name}</td>
                  <td>
                    <span className="pill">{s.kind === "live" ? "Live" : "Vídeos"}</span>
                  </td>
                  <td className="muted">{date(s.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Nenhum roteiro ainda.</p>
        )}
      </div>
    </>
  );
}

export function ScriptPage() {
  const { id = "" } = useParams();
  const { data, error, loading } = useLoad(() => api<ScriptDetail>(`/api/scripts/${id}`), [id]);
  if (loading) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  return data.kind === "live" ? (
    <LiveView s={data} out={data.output as LiveScript} />
  ) : (
    <VideosView s={data} out={data.output as VideoScript} />
  );
}

function VideosView({ s, out }: { s: ScriptDetail; out: VideoScript }) {
  const all = [
    "GANCHOS",
    ...out.hooks.map((h, i) => `${i + 1}. ${h.text}`),
    "",
    "CORPOS",
    ...out.bodies.map((b, i) => `${i + 1}. ${b.title}: ${b.text}`),
    "",
    "CTAs",
    ...out.ctas.map((c, i) => `${i + 1}. ${c.text}`),
  ].join("\n");
  return (
    <>
      <PageHead
        title={s.product_name}
        sub="Roteiro para o Multiplicador: grave cada item como um vídeo separado."
        actions={
          <>
            <CopyButton text={all} label="Copiar tudo" />
            {!DEMO && (
              <button className="btn no-print" onClick={() => window.print()}>
                Imprimir / PDF
              </button>
            )}
            <Link className="btn primary no-print" to="/app/multiplicador">
              Ir para o Multiplicador
            </Link>
          </>
        }
      />
      <div className="grid cols-3">
        <Section title={`${out.hooks.length} ganchos`} tone="#ffb79e">
          {out.hooks.map((h, i) => (
            <Item key={i} n={i + 1} text={h.text} meta={h.technique} />
          ))}
        </Section>
        <Section title={`${out.bodies.length} corpos`} tone="#b7d3ff">
          {out.bodies.map((b, i) => (
            <Item key={i} n={i + 1} text={b.text} meta={b.title} />
          ))}
        </Section>
        <Section title={`${out.ctas.length} CTAs`} tone="#a5f5d7">
          {out.ctas.map((c, i) => (
            <Item key={i} n={i + 1} text={c.text} />
          ))}
        </Section>
      </div>
      {out.recordingTips.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Dicas de gravação</h3>
          <ul>
            {out.recordingTips.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

function Section({ title, tone, children }: { title: string; tone: string; children: React.ReactNode }) {
  return (
    <div className="card">
      <h3 style={{ color: tone }}>{title}</h3>
      {children}
    </div>
  );
}

function Item({ n, text, meta }: { n: number; text: string; meta?: string }) {
  return (
    <div className="script-item">
      <span className="n">{n}</span>
      <div className="stack" style={{ gap: 4, flex: 1 }}>
        {meta && <span className="faint small">{meta}</span>}
        <span>{text}</span>
      </div>
      <span className="no-print">
        <CopyButton text={text} label="⧉" />
      </span>
    </div>
  );
}

const STAGE: Record<string, string> = {
  abertura: "Abertura",
  dor: "Dor",
  desejo: "Desejo",
  detalhe: "Detalhe",
  prova: "Prova",
  oferta: "Oferta",
  cta: "CTA",
  interacao: "Interação",
};

function LiveView({ s, out }: { s: ScriptDetail; out: LiveScript }) {
  const [prompter, setPrompter] = useState(false);
  return (
    <>
      <PageHead
        title={out.title}
        sub={`Live de ${s.input.liveMinutes} minutos · ${s.product_name}`}
        actions={
          <>
            {!DEMO && (
              <button className="btn no-print" onClick={() => window.print()}>
                Imprimir / PDF
              </button>
            )}
            <button className="btn primary no-print" onClick={() => setPrompter(true)}>
              Abrir teleprompter
            </button>
          </>
        }
      />
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(260px, 1fr)", alignItems: "start" }}>
        <div className="card">
          {out.blocks.map((b, i) => (
            <div className="script-item" key={i}>
              <span className="n">{b.minute}'</span>
              <div className="stack" style={{ gap: 4 }}>
                <span className="row small">
                  <span className="pill hot">{STAGE[b.stage] ?? b.stage}</span>
                  <strong>{b.title}</strong>
                </span>
                <span>{b.text}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="stack">
          <div className="card">
            <h3>Dúvidas do chat</h3>
            {out.objections.map((o, i) => (
              <div key={i} className="script-item" style={{ display: "block" }}>
                <strong>{o.question}</strong>
                <div className="muted">{o.answer}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <h3>Antes de entrar ao vivo</h3>
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {out.checklist.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      {prompter && <Teleprompter blocks={out.blocks} onClose={() => setPrompter(false)} />}
    </>
  );
}

function Teleprompter({ blocks, onClose }: { blocks: LiveScript["blocks"]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [speed, setSpeed] = useState(1);
  const [running, setRunning] = useState(true);
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => ref.current?.scrollBy({ top: speed }), 30);
    return () => clearInterval(t);
  }, [speed, running]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === " ") {
        e.preventDefault();
        setRunning((r) => !r);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div className="teleprompter" ref={ref}>
        {blocks.map((b, i) => (
          <div className="block" key={i}>
            <div className="stage">
              {b.minute}' · {STAGE[b.stage] ?? b.stage}
            </div>
            {b.text}
          </div>
        ))}
        <div style={{ height: "60vh" }} />
      </div>
      <div className="teleprompter-controls">
        <button className="btn sm" onClick={() => setSpeed((s) => Math.max(0.5, s - 0.5))}>
          − lento
        </button>
        <button className="btn sm primary" onClick={() => setRunning((r) => !r)}>
          {running ? "Pausar" : "Continuar"}
        </button>
        <button className="btn sm" onClick={() => setSpeed((s) => Math.min(6, s + 0.5))}>
          + rápido
        </button>
        <button className="btn sm" onClick={onClose}>
          Fechar
        </button>
      </div>
    </>
  );
}
