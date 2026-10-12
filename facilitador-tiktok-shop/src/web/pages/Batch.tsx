import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { api, DEMO, type BatchDetail, type Output } from "../api.ts";
import { CopyButton, ErrorBox, Loading, PageHead, useLoad } from "../components/ui.tsx";
import { bytes, date, weekday } from "../format.ts";
import { LABEL_INFO, type OriginalityLabel } from "../../shared/combos.ts";
import { fileName, render, renderAndSave, useJob } from "../demo/downloadQueue.ts";
import { saveFile, unlockAudio } from "../demo/render.ts";
import { makeZip } from "../demo/zip.ts";

const ZIP_LIMIT = 20;

/** Demonstração: monta os vídeos no navegador, um por vez, e entrega um ZIP. */
function DemoZipButton({ outputs }: { outputs: Output[] }) {
  const [state, setState] = useState<{ done: number; total: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const list = outputs.filter((o) => o.sequence).slice(0, ZIP_LIMIT);
  async function go() {
    unlockAudio();
    setError(null);
    setState({ done: 0, total: list.length });
    try {
      const files: { name: string; data: Blob }[] = [];
      for (const [n, o] of list.entries()) {
        const r = await render(o.id, o.sequence!);
        files.push({ name: fileName(o.position, r.ext), data: r.blob });
        setState({ done: n + 1, total: list.length });
      }
      const csv = [
        "ordem;data sugerida;selo;arquivo;legenda",
        ...list.map((o, n) => [o.position + 1, date(o.suggestedDate), LABEL_INFO[o.label].title, files[n]!.name, `"${o.caption.replace(/"/g, '""')}"`].join(";")),
      ].join("\n");
      files.push({ name: "ordem-de-postagem.csv", data: new Blob(["\uFEFF" + csv], { type: "text/csv" }) });
      await saveFile("videos.zip", await makeZip(files));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setState(null);
    }
  }
  return (
    <div className="stack" style={{ gap: 6, alignItems: "flex-end" }}>
      <button className="btn primary" onClick={go} disabled={!!state}>
        {state ? `Montando ${state.done}/${state.total}...` : outputs.length > ZIP_LIMIT ? `⬇ Baixar os ${ZIP_LIMIT} primeiros (ZIP)` : "⬇ Baixar todos (ZIP)"}
      </button>
      {error && <span className="small" style={{ color: "var(--rose)" }}>{error}</span>}
    </div>
  );
}

function DemoDownload({ output: o }: { output: Output }) {
  const job = useJob(o.id);
  const [error, setError] = useState<string | null>(null);
  async function go() {
    unlockAudio();
    setError(null);
    try {
      await renderAndSave(o.id, o.position, o.sequence!);
    } catch (err) {
      setError((err as Error).message);
    }
  }
  if (job.status === "rendering" || job.status === "queued") {
    const pct = job.status === "rendering" ? Math.round(job.progress * 100) : 0;
    return (
      <div className="stack" style={{ gap: 6 }}>
        <div className="progress"><div style={{ width: `${Math.max(3, pct)}%` }} /></div>
        <span className="small muted">{job.status === "queued" ? "Na fila..." : `Montando o vídeo... ${pct}% · deixe a tela aberta`}</span>
      </div>
    );
  }
  return (
    <div className="stack" style={{ gap: 6 }}>
      <button className="btn primary" style={{ width: "100%" }} onClick={go}>
        ⬇ {job.status === "ready" ? "Baixar de novo" : "Baixar vídeo pronto"}
      </button>
      {(error || job.status === "error") && (
        <span className="small" style={{ color: "var(--rose)" }}>{error ?? (job.status === "error" ? job.message : "")}</span>
      )}
    </div>
  );
}

export function BatchPage() {
  const { id = "" } = useParams();
  const { data, error, loading, reload } = useLoad(() => api<BatchDetail>(`/api/batches/${id}`), [id]);
  const [filter, setFilter] = useState<OriginalityLabel | "all">("all");
  const status = data?.batch.status;

  useEffect(() => {
    if (status !== "queued" && status !== "processing") return;
    const t = setInterval(() => void reload(), 3000);
    return () => clearInterval(t);
  }, [status, reload]);

  if (loading) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  const { batch, outputs } = data;
  const pct = Math.round((batch.done / Math.max(1, batch.total)) * 100);
  const shown = filter === "all" ? outputs : outputs.filter((o) => o.label === filter);

  return (
    <>
      <PageHead
        title={`${batch.total} vídeos`}
        sub={
          <>
            <Link to={`/app/multiplicador/${batch.projectId}`}>{batch.projectName}</Link> · {batch.postsPerDay} por dia a
            partir de {date(batch.startDate)}
          </>
        }
        actions={
          batch.zipUrl ? (
            <a className="btn primary" href={batch.zipUrl}>
              ⬇ Baixar todos (ZIP{batch.zipSizeBytes ? `, ${bytes(batch.zipSizeBytes)}` : ""})
            </a>
          ) : DEMO && status === "done" ? (
            <DemoZipButton outputs={outputs} />
          ) : null
        }
      />

      {(status === "queued" || status === "processing") && (
        <div className="card stack">
          <div className="row between">
            <strong>{status === "queued" ? "Na fila, já vai começar..." : "Montando seus vídeos..."}</strong>
            <span className="muted">
              {batch.done}/{batch.total}
            </span>
          </div>
          <div className="progress">
            <div style={{ width: `${status === "queued" ? 2 : Math.max(4, pct)}%` }} />
          </div>
          <p className="muted small" style={{ margin: 0 }}>
            Primeiro padronizamos cada pedaço (formato, tamanho e volume), depois juntamos as combinações. Pode fechar a
            página: o lote continua sendo montado.
          </p>
        </div>
      )}
      {status === "error" && <div className="alert error">{batch.error ?? "Não foi possível montar os vídeos."} A cota foi devolvida.</div>}
      {status === "expired" && (
        <div className="alert warn">
          Os vídeos deste lote expiraram. Os pedaços continuam no projeto: gere um lote novo quando quiser.
        </div>
      )}

      {status === "done" && (
        <>
          {DEMO && (
            <div className="alert warn small" style={{ marginBottom: 12 }}>
              Toque em <strong>Baixar vídeo pronto</strong>: o navegador monta o vídeo final (gancho + corpo + CTA, com
              áudio) e salva no seu aparelho. Leva o tempo do próprio vídeo, então deixe a tela aberta enquanto monta.
            </div>
          )}
          <div className="alert info small" style={{ marginBottom: 16 }}>
            Poste na ordem. O ZIP traz a planilha <strong>ordem-de-postagem.csv</strong> com data, selo e legenda de cada
            vídeo.{DEMO ? "" : ` Disponível até ${batch.expiresAt ? date(batch.expiresAt) : "—"}.`}
          </div>
          <div className="row" style={{ marginBottom: 16 }}>
            {(["all", "original", "variacao", "parecido"] as const).map((f) => (
              <button key={f} className={`btn sm ${filter === f ? "primary" : ""}`} onClick={() => setFilter(f)}>
                {f === "all" ? `Todos (${outputs.length})` : `${LABEL_INFO[f].title} (${outputs.filter((o) => o.label === f).length})`}
              </button>
            ))}
          </div>
          <div className="video-grid">
            {shown.map((o) => (
              <VideoCard key={o.id} output={o} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

/** Demonstração: toca gancho → corpo → CTA em sequência, como se fosse um vídeo só. */
function SequencePlayer({ urls }: { urls: string[] }) {
  const ref = useRef<HTMLVideoElement>(null);
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const keepPlaying = useRef(false);
  const parts = ["Gancho", "Corpo", "CTA"];
  useEffect(() => {
    if (keepPlaying.current) void ref.current?.play();
  }, [i]);
  return (
    <div style={{ position: "relative" }}>
      <video
        ref={ref}
        src={urls[i]}
        playsInline
        preload="metadata"
        onClick={() => (ref.current?.paused ? void ref.current.play() : ref.current?.pause())}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          const next = (i + 1) % urls.length;
          keepPlaying.current = next !== 0;
          setI(next);
        }}
      />
      <span className="pill" style={{ position: "absolute", top: 8, left: 8 }}>{parts[i] ?? ""}</span>
      {!playing && (
        <button
          className="btn icon"
          style={{ position: "absolute", left: "50%", top: "50%", transform: "translate(-50%, -50%)" }}
          onClick={() => void ref.current?.play()}
          aria-label="Assistir"
        >
          ▶
        </button>
      )}
    </div>
  );
}

function VideoCard({ output: o }: { output: Output }) {
  const [caption, setCaption] = useState(o.caption);
  const [saved, setSaved] = useState(o.caption);
  return (
    <div className="card video-card">
      <div className="row between">
        <strong>#{o.position + 1}</strong>
        <span className={`pill ${o.label}`} title={LABEL_INFO[o.label].tip}>
          {LABEL_INFO[o.label].title}
        </span>
      </div>
      {o.url && <video src={o.url} controls playsInline preload="none" />}
      {!o.url && o.sequence && <SequencePlayer urls={o.sequence} />}
      <div className="small">
        📅 {weekday(o.suggestedDate)}, {date(o.suggestedDate)}
      </div>
      <div className="parts">
        {o.parts.hook} + {o.parts.body} + {o.parts.cta}
      </div>
      {o.label !== "original" && <div className="faint small">{LABEL_INFO[o.label].tip}</div>}
      <textarea
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        onBlur={async () => {
          if (caption === saved) return;
          await api(`/api/outputs/${o.id}`, { method: "PATCH", body: { caption } });
          setSaved(caption);
        }}
        placeholder="Legenda do post"
      />
      {o.downloadUrl && (
        <a className="btn primary" style={{ width: "100%" }} href={o.downloadUrl}>
          ⬇ Baixar vídeo pronto
        </a>
      )}
      {!o.downloadUrl && o.sequence && <DemoDownload output={o} />}
      <CopyButton text={caption} label="Copiar legenda" />
    </div>
  );
}
