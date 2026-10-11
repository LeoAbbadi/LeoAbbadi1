import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import {
  api,
  uploadFile,
  type BatchSummary,
  type Clip,
  type ProjectDetail,
  type ProjectSummary,
  type Slot,
} from "../api.ts";
import { ErrorBox, Loading, PageHead, useLoad } from "../components/ui.tsx";
import { useSession } from "../session.tsx";
import { date, today } from "../format.ts";
import { SLOT_LIMITS, MAX_CLIP_BYTES } from "../../shared/plans.ts";
import { planVideos } from "../../shared/combos.ts";

export function ProjectsPage() {
  const { data, error, loading } = useLoad(() => api<ProjectSummary[]>("/api/projects"), []);
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [productName, setProductName] = useState("");
  const [createError, setCreateError] = useState<unknown>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      const p = await api<{ id: string }>("/api/projects", { body: { name, productName } });
      navigate(`/app/multiplicador/${p.id}`);
    } catch (err) {
      setCreateError(err);
    }
  }

  return (
    <>
      <PageHead
        title="Multiplicador"
        sub="Um projeto por produto. Envie os pedaços uma vez e gere quantos lotes quiser."
      />
      <form className="card stack" onSubmit={create} style={{ marginBottom: 24 }}>
        <h3>Novo projeto</h3>
        <div className="grid cols-2">
          <label className="field">
            Nome do projeto
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex.: Legging outubro" required />
          </label>
          <label className="field">
            Produto
            <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Ex.: Legging cintura alta" />
            <span className="hint">Usado para criar as hashtags das legendas.</span>
          </label>
        </div>
        <ErrorBox error={createError} />
        <div>
          <button className="btn primary">Criar projeto</button>
        </div>
      </form>
      <ErrorBox error={error} />
      {loading ? (
        <Loading />
      ) : data && data.length ? (
        <div className="grid cols-3">
          {data.map((p) => (
            <Link key={p.id} to={`/app/multiplicador/${p.id}`} className="card hover stack" style={{ textDecoration: "none" }}>
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              <div className="muted small">{p.product_name || "Sem produto definido"}</div>
              <div className="row small">
                <span className="pill">{p.clips} pedaços</span>
                <span className="pill">{p.videos} vídeos gerados</span>
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="empty">Nenhum projeto ainda. Crie o primeiro acima.</div>
      )}
    </>
  );
}

const SLOT_INFO: Record<Slot, { title: string; hint: string; placeholder: string }> = {
  hook: { title: "Ganchos", hint: "2 a 4 segundos. O que prende nos primeiros segundos.", placeholder: "Texto do gancho (vira a legenda)" },
  body: { title: "Corpos", hint: "15 a 25 segundos. Mostre o produto.", placeholder: "Anotação (opcional)" },
  cta: { title: "CTAs", hint: "3 a 5 segundos. Chame para o carrinho.", placeholder: "Anotação (opcional)" },
};

interface Uploading {
  id: string;
  name: string;
  pct: number;
  error?: string;
}

function DropZone({ slot, clips, projectId, onChange }: { slot: Slot; clips: Clip[]; projectId: string; onChange: () => void }) {
  const [drag, setDrag] = useState(false);
  const [uploads, setUploads] = useState<Uploading[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const info = SLOT_INFO[slot];
  const free = SLOT_LIMITS[slot] - clips.length - uploads.filter((u) => !u.error).length;

  async function send(files: FileList | File[]) {
    const list = [...files].filter((f) => f.type.startsWith("video/")).slice(0, Math.max(0, free));
    for (const file of list) {
      const tmp = crypto.randomUUID();
      const update = (patch: Partial<Uploading>) => setUploads((u) => u.map((x) => (x.id === tmp ? { ...x, ...patch } : x)));
      setUploads((u) => [...u, { id: tmp, name: file.name, pct: 0 }]);
      try {
        if (file.size > MAX_CLIP_BYTES) throw new Error("Máximo de 300 MB por vídeo.");
        const { clipId, uploadUrl } = await api<{ clipId: string; uploadUrl: string }>(`/api/projects/${projectId}/clips`, {
          body: { slot, filename: file.name, contentType: file.type || "video/mp4", size: file.size },
        });
        await uploadFile(uploadUrl, file, (pct) => update({ pct }));
        await api(`/api/clips/${clipId}/complete`, { body: {} });
        setUploads((u) => u.filter((x) => x.id !== tmp));
        onChange();
      } catch (err) {
        update({ error: (err as Error).message });
      }
    }
  }

  return (
    <div
      className={`dropzone ${slot} ${drag ? "drag" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        void send(e.dataTransfer.files);
      }}
    >
      <header>
        <span className="tag">{info.title}</span>
        <span className="pill">
          {clips.length}/{SLOT_LIMITS[slot]}
        </span>
      </header>
      <div className="faint small">{info.hint}</div>
      {clips.map((c, i) => (
        <ClipRow key={c.id} clip={c} index={i} placeholder={info.placeholder} onChange={onChange} />
      ))}
      {uploads.map((u) => (
        <div key={u.id} className="clip" style={{ gridTemplateColumns: "1fr auto" }}>
          <div className="stack" style={{ gap: 6 }}>
            <div className="name">{u.name}</div>
            {u.error ? <div className="small" style={{ color: "var(--rose)" }}>{u.error}</div> : <div className="progress"><div style={{ width: `${u.pct}%` }} /></div>}
          </div>
          {u.error ? (
            <button className="btn sm ghost" onClick={() => setUploads((x) => x.filter((y) => y.id !== u.id))}>
              ✕
            </button>
          ) : (
            <span className="small muted">{u.pct}%</span>
          )}
        </div>
      ))}
      {free > 0 && (
        <div className="add-clip" onClick={() => input.current?.click()} role="button" tabIndex={0}>
          + Arraste ou escolha vídeos
          <input
            ref={input}
            type="file"
            accept="video/*"
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files) void send(e.target.files);
              e.target.value = "";
            }}
          />
        </div>
      )}
    </div>
  );
}

function ClipRow({ clip, index, placeholder, onChange }: { clip: Clip; index: number; placeholder: string; onChange: () => void }) {
  const [label, setLabel] = useState(clip.label);
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="clip">
      <video src={`${clip.previewUrl}#t=0.1`} muted playsInline preload="metadata" onMouseEnter={(e) => void e.currentTarget.play()} onMouseLeave={(e) => e.currentTarget.pause()} />
      <div className="stack" style={{ gap: 6, minWidth: 0 }}>
        <div className="name" title={clip.name}>
          {index + 1}. {clip.name}
        </div>
        <input
          value={label}
          placeholder={placeholder}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={() => label !== clip.label && api(`/api/clips/${clip.id}`, { method: "PATCH", body: { label } })}
        />
        {error && <div className="small" style={{ color: "var(--rose)" }}>{error}</div>}
      </div>
      <button
        className="btn sm ghost danger"
        title="Remover"
        onClick={async () => {
          if (!confirm("Remover este vídeo do projeto?")) return;
          try {
            await api(`/api/clips/${clip.id}`, { method: "DELETE" });
            onChange();
          } catch (err) {
            setError((err as Error).message);
          }
        }}
      >
        ✕
      </button>
    </div>
  );
}

const STATUS: Record<BatchSummary["status"], string> = {
  queued: "Na fila",
  processing: "Montando",
  done: "Pronto",
  error: "Erro",
  expired: "Expirado",
};

export function ProjectPage() {
  const { id = "" } = useParams();
  const { me, refresh } = useSession();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useLoad(() => api<ProjectDetail>(`/api/projects/${id}`), [id]);
  const [count, setCount] = useState<number | null>(null);
  const [postsPerDay, setPostsPerDay] = useState(2);
  const [startDate, setStartDate] = useState(today());
  const [busy, setBusy] = useState(false);
  const [genError, setGenError] = useState<unknown>(null);

  const bySlot = (s: Slot) => data?.clips.filter((c) => c.slot === s) ?? [];
  const hooks = bySlot("hook");
  const bodies = bySlot("body");
  const ctas = bySlot("cta");
  const possible = hooks.length * bodies.length * ctas.length;
  const remaining = me ? me.limits.videosPerMonth - me.usage.videos : 0;
  const max = Math.max(0, Math.min(possible, me?.limits.maxVideosPerBatch ?? 0, remaining));
  const recommended = Math.min(max, hooks.length * bodies.length);
  const chosen = Math.min(count ?? recommended, max);
  const preview = useMemo(
    () =>
      planVideos(
        hooks.map((c) => c.id),
        bodies.map((c) => c.id),
        ctas.map((c) => c.id),
        chosen,
        postsPerDay,
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [hooks.length, bodies.length, ctas.length, chosen, postsPerDay],
  );
  const counts = { original: 0, variacao: 0, parecido: 0 };
  preview.forEach((v) => counts[v.label]++);
  const days = preview.length ? preview[preview.length - 1]!.dayOffset + 1 : 0;
  const running = data?.batches.some((b) => b.status === "queued" || b.status === "processing");

  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => void reload(), 4000);
    return () => clearInterval(t);
  }, [running, reload]);

  async function generate() {
    setBusy(true);
    setGenError(null);
    try {
      const r = await api<{ batchId: string }>(`/api/projects/${id}/batches`, { body: { count: chosen, postsPerDay, startDate } });
      await refresh();
      navigate(`/app/lotes/${r.batchId}`);
    } catch (err) {
      setGenError(err);
      setBusy(false);
    }
  }

  if (loading) return <Loading />;
  if (!data) return <ErrorBox error={error} />;

  return (
    <>
      <PageHead
        title={data.project.name}
        sub={data.project.product_name || undefined}
        actions={
          <button
            className="btn sm ghost danger"
            onClick={async () => {
              if (!confirm("Apagar o projeto, os pedaços e todos os vídeos gerados?")) return;
              await api(`/api/projects/${id}`, { method: "DELETE" });
              navigate("/app/multiplicador");
            }}
          >
            Apagar projeto
          </button>
        }
      />
      <div className="alert info small" style={{ marginBottom: 16 }}>
        Grave na vertical e com boa luz. Cada pedaço deve funcionar sozinho: qualquer gancho vai ser seguido de qualquer
        corpo. Precisa de ideias? <Link to="/app/roteiros">Gere um roteiro com IA</Link>.
      </div>
      <div className="dropzones">
        {(["hook", "body", "cta"] as Slot[]).map((s) => (
          <DropZone key={s} slot={s} clips={bySlot(s)} projectId={id} onChange={() => void reload()} />
        ))}
      </div>

      <div className="card pad-lg stack" style={{ marginTop: 24, gap: 18 }}>
        <div className="row between">
          <h3 style={{ margin: 0 }}>Gerar vídeos</h3>
          <span className="muted small">
            {hooks.length} × {bodies.length} × {ctas.length} = <strong>{possible}</strong> combinações possíveis
          </span>
        </div>
        {possible === 0 ? (
          <p className="muted" style={{ margin: 0 }}>Envie pelo menos 1 gancho, 1 corpo e 1 CTA.</p>
        ) : max === 0 ? (
          <div className="alert warn">
            Sua cota de vídeos deste mês acabou. <Link to="/planos">Veja os planos</Link>.
          </div>
        ) : (
          <>
            <div className="grid cols-3">
              <label className="field">
                Quantos vídeos
                <input type="range" min={1} max={max} value={chosen} onChange={(e) => setCount(Number(e.target.value))} />
                <span className="hint">
                  <strong style={{ color: "var(--text)", fontSize: "1.2rem" }}>{chosen}</strong> de até {max}
                  {recommended < max && (
                    <>
                      {" · "}
                      <button className="link" type="button" onClick={() => setCount(recommended)}>
                        usar {recommended} (sem Parecidos)
                      </button>
                    </>
                  )}
                </span>
              </label>
              <label className="field">
                Posts por dia
                <select value={postsPerDay} onChange={(e) => setPostsPerDay(Number(e.target.value))}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n} por dia
                    </option>
                  ))}
                </select>
                <span className="hint">Dá conteúdo para {days} dias.</span>
              </label>
              <label className="field">
                Começar em
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </label>
            </div>
            <div className="row">
              <span className="pill original">{counts.original} Originais</span>
              <span className="pill variacao">{counts.variacao} Variações</span>
              <span className="pill parecido">{counts.parecido} Parecidos</span>
              <span className="spacer" />
              <span className="muted small">Restam {remaining.toLocaleString("pt-BR")} vídeos no seu plano este mês</span>
            </div>
            <ErrorBox error={genError} />
            <div>
              <button className="btn primary big" onClick={generate} disabled={busy || !!running}>
                {running ? "Já tem um lote sendo montado" : busy ? "Enviando..." : `Gerar ${chosen} vídeos`}
              </button>
            </div>
          </>
        )}
      </div>

      {data.batches.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <h3>Lotes gerados</h3>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Criado em</th>
                  <th>Vídeos</th>
                  <th>Situação</th>
                  <th>Disponível até</th>
                </tr>
              </thead>
              <tbody>
                {data.batches.map((b) => (
                  <tr key={b.id} className="clickable" onClick={() => navigate(`/app/lotes/${b.id}`)}>
                    <td>{date(b.createdAt)}</td>
                    <td>{b.total}</td>
                    <td>
                      {STATUS[b.status]}
                      {b.status === "processing" && ` (${b.done}/${b.total})`}
                    </td>
                    <td className="muted">{b.expiresAt ? date(b.expiresAt) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
