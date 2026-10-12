import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { api, DEMO, type BatchDetail, type Output } from "../api.ts";
import { CopyButton, ErrorBox, Loading, PageHead, useLoad } from "../components/ui.tsx";
import { bytes, date, weekday } from "../format.ts";
import { LABEL_INFO, type OriginalityLabel } from "../../shared/combos.ts";
import { fileName, render, useJob } from "../demo/downloadQueue.ts";
import { prepareForRender, saveFile, warmUpDownloads } from "../demo/render.ts";
import { makeZip } from "../demo/zip.ts";

const ZIP_LIMIT = 20;

type SaveMsg = { kind: "ok" | "error"; text: string } | null;

function SaveNote({ msg }: { msg: SaveMsg }) {
  if (!msg) return null;
  return (
    <span className="small" style={{ color: msg.kind === "ok" ? "var(--mint)" : "var(--rose)" }} role="status">
      {msg.text}
    </span>
  );
}

async function trySave(name: string, blob: Blob, setMsg: (m: SaveMsg) => void) {
  setMsg(null);
  try {
    const r = await saveFile(name, blob);
    if (r === "saved") setMsg({ kind: "ok", text: "Pronto! Procure em Downloads (ou em Fotos, se escolheu Salvar vídeo)." });
  } catch (err) {
    setMsg({ kind: "error", text: (err as Error).message });
  }
}

/** Demonstração: monta os vídeos no navegador, um por vez, e entrega um ZIP. */
function DemoZipButton({ outputs }: { outputs: Output[] }) {
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [zip, setZip] = useState<Blob | null>(null);
  const [msg, setMsg] = useState<SaveMsg>(null);
  const list = outputs.filter((o) => o.sequence).slice(0, ZIP_LIMIT);
  async function build() {
    prepareForRender();
    setMsg(null);
    setProgress({ done: 0, total: list.length });
    try {
      const files: { name: string; data: Blob }[] = [];
      for (const [n, o] of list.entries()) {
        const r = await render(o.id, o.sequence!);
        files.push({ name: fileName(o.position, r.ext), data: r.blob });
        setProgress({ done: n + 1, total: list.length });
      }
      const csv = [
        "ordem;data sugerida;selo;arquivo;legenda",
        ...list.map((o, n) => [o.position + 1, date(o.suggestedDate), LABEL_INFO[o.label].title, files[n]!.name, `"${o.caption.replace(/"/g, '""')}"`].join(";")),
      ].join("\n");
      files.push({ name: "ordem-de-postagem.csv", data: new Blob(["\uFEFF" + csv], { type: "text/csv" }) });
      setZip(await makeZip(files));
    } catch (err) {
      setMsg({ kind: "error", text: (err as Error).message });
    } finally {
      setProgress(null);
    }
  }
  const label = outputs.length > ZIP_LIMIT ? `os ${ZIP_LIMIT} primeiros` : "todos";
  return (
    <div className="stack" style={{ gap: 6, alignItems: "flex-end" }}>
      {zip ? (
        <button className="btn primary" onClick={() => void trySave("videos.zip", zip, setMsg)}>
          ⬇ Salvar ZIP no aparelho ({list.length} vídeos)
        </button>
      ) : (
        <button className="btn primary" onClick={() => void build()} disabled={!!progress}>
          {progress ? `Montando ${progress.done}/${progress.total}... deixe a tela aberta` : `⬇ Baixar ${label} (ZIP)`}
        </button>
      )}
      <SaveNote msg={msg} />
    </div>
  );
}

function DemoDownload({ output: o }: { output: Output }) {
  const job = useJob(o.id);
  const [msg, setMsg] = useState<SaveMsg>(null);
  function start() {
    prepareForRender(); // precisa ser no toque para o vídeo sair com som (iPhone)
    setMsg(null);
    render(o.id, o.sequence!).catch(() => undefined);
  }
  if (job.status === "rendering" || job.status === "queued") {
    const pct = job.status === "rendering" ? Math.round(job.progress * 100) : 0;
    return (
      <div className="stack" style={{ gap: 6 }}>
        <div className="progress"><div style={{ width: `${Math.max(3, pct)}%` }} /></div>
        <span className="small muted">
          {job.status === "queued"
            ? "Na fila..."
            : job.phase === "preparing"
              ? "Preparando os vídeos..."
              : job.phase === "finishing"
                ? "Finalizando o arquivo... só mais uns segundos"
                : `Montando o vídeo... ${pct}% · deixe a tela aberta`}
        </span>
      </div>
    );
  }
  if (job.status === "ready") {
    return (
      <div className="stack" style={{ gap: 6 }}>
        <span className="small mint">✓ Vídeo montado</span>
        <button className="btn primary" style={{ width: "100%" }} onClick={() => void trySave(fileName(o.position, job.result.ext), job.result.blob, setMsg)}>
          ⬇ Salvar no aparelho
        </button>
        <SaveNote msg={msg} />
      </div>
    );
  }
  return (
    <div className="stack" style={{ gap: 6 }}>
      <button className="btn primary" style={{ width: "100%" }} onClick={start}>
        ⬇ {job.status === "error" ? "Tentar de novo" : "Baixar vídeo pronto"}
      </button>
      {job.status === "error" && <SaveNote msg={{ kind: "error", text: job.message }} />}
    </div>
  );
}

export function BatchPage() {
  const { id = "" } = useParams();
  const { data, error, loading, reload } = useLoad(() => api<BatchDetail>(`/api/batches/${id}`), [id]);
  const [filter, setFilter] = useState<OriginalityLabel | "all">("all");
  const status = data?.batch.status;
  useEffect(() => {
    if (DEMO) warmUpDownloads();
  }, []);

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
              áudio). Leva o tempo do próprio vídeo, então deixe a tela aberta. Quando terminar, toque em{" "}
              <strong>Salvar no aparelho</strong>.
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
        preload="none"
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
