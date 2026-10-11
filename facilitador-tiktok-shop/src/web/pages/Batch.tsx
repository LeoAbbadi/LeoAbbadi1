import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { api, type BatchDetail, type Output } from "../api.ts";
import { CopyButton, ErrorBox, Loading, PageHead, useLoad } from "../components/ui.tsx";
import { bytes, date, weekday } from "../format.ts";
import { LABEL_INFO, type OriginalityLabel } from "../../shared/combos.ts";

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
          batch.zipUrl && (
            <a className="btn primary" href={batch.zipUrl}>
              Baixar tudo (ZIP{batch.zipSizeBytes ? `, ${bytes(batch.zipSizeBytes)}` : ""})
            </a>
          )
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
          <div className="alert info small" style={{ marginBottom: 16 }}>
            Poste na ordem. O ZIP traz a planilha <strong>ordem-de-postagem.csv</strong> com data, selo e legenda de cada
            vídeo. Disponível até {batch.expiresAt ? date(batch.expiresAt) : "—"}.
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
      <div className="row">
        <CopyButton text={caption} label="Copiar legenda" />
        {o.downloadUrl && (
          <a className="btn sm" href={o.downloadUrl}>
            Baixar
          </a>
        )}
      </div>
    </div>
  );
}
