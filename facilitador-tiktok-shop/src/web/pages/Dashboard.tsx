import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { api, type Product, type ProjectSummary } from "../api.ts";
import { ErrorBox, Meter, PageHead, useLoad } from "../components/ui.tsx";
import { useSession } from "../session.tsx";
import { compactBRL, date } from "../format.ts";
import { Growth, Thumb } from "./Products.tsx";
import { PLANS } from "../../shared/plans.ts";

export function DashboardPage() {
  const { me } = useSession();
  const navigate = useNavigate();
  const projects = useLoad(() => api<ProjectSummary[]>("/api/projects"), []);
  const trending = useLoad(() => api<{ items: Product[] }>("/api/products?sort=growth&limit=5"), []);
  if (!me) return null;
  return (
    <>
      <PageHead title={`Olá, ${me.user.name.split(" ")[0]}!`} sub="O que vamos postar hoje?" />
      <div className="grid cols-3" style={{ marginBottom: 24 }}>
        <Link to="/app/multiplicador" className="card hover stack" style={{ textDecoration: "none" }}>
          <span className="pill hot">Multiplicador</span>
          <h3 style={{ margin: 0 }}>Transformar pedaços em vídeos</h3>
          <span className="muted small">Grave ganchos, corpos e CTAs e gere até {me.limits.maxVideosPerBatch} vídeos por lote.</span>
        </Link>
        <Link to="/app/produtos" className="card hover stack" style={{ textDecoration: "none" }}>
          <span className="pill hot">Produtos</span>
          <h3 style={{ margin: 0 }}>Ver o que está vendendo</h3>
          <span className="muted small">Ranking por faturamento e o que explodiu nas últimas 24h.</span>
        </Link>
        <Link to="/app/roteiros" className="card hover stack" style={{ textDecoration: "none" }}>
          <span className="pill hot">Roteiros</span>
          <h3 style={{ margin: 0 }}>Gerar roteiro com IA</h3>
          <span className="muted small">10 ganchos, 5 corpos e 3 CTAs, ou o roteiro inteiro da sua live.</span>
        </Link>
      </div>
      <div className="grid cols-2">
        <div className="card stack">
          <div className="row between">
            <h3 style={{ margin: 0 }}>Seu mês</h3>
            <span className="pill">{PLANS[me.user.plan].name}</span>
          </div>
          <Meter label="Vídeos gerados" used={me.usage.videos} limit={me.limits.videosPerMonth} />
          <Meter label="Roteiros com IA" used={me.usage.scripts} limit={me.limits.scriptsPerMonth} />
          {me.user.plan !== "pro" && (
            <Link to="/planos" className="btn primary sm" style={{ alignSelf: "flex-start" }}>
              Aumentar limites
            </Link>
          )}
        </div>
        <div className="card">
          <h3>Explodindo nas últimas 24h</h3>
          <ErrorBox error={trending.error} />
          {trending.data?.items.map((p) => (
            <div key={p.id} className="row" style={{ padding: "8px 0", cursor: "pointer", flexWrap: "nowrap" }} onClick={() => navigate(`/app/produtos/${p.id}`)}>
              <Thumb p={p} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name}</div>
                <div className="faint small">{compactBRL(p.gmv_cents)} em 7 dias</div>
              </div>
              <Growth value={p.growth_pct_1d} />
            </div>
          ))}
        </div>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <div className="row between">
          <h3 style={{ margin: 0 }}>Projetos recentes</h3>
          <Link to="/app/multiplicador" className="btn sm">
            Novo projeto
          </Link>
        </div>
        {projects.data?.length ? (
          <table className="table" style={{ marginTop: 8 }}>
            <tbody>
              {projects.data.slice(0, 5).map((p) => (
                <tr key={p.id} className="clickable" onClick={() => navigate(`/app/multiplicador/${p.id}`)}>
                  <td>{p.name}</td>
                  <td className="muted">{p.clips} pedaços</td>
                  <td className="muted">{p.videos} vídeos</td>
                  <td className="muted">{date(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted" style={{ marginTop: 12 }}>Nenhum projeto ainda.</p>
        )}
      </div>
    </>
  );
}

export function AccountPage() {
  const { me, logout } = useSession();
  const [params] = useSearchParams();
  const [error, setError] = useState<unknown>(null);
  if (!me) return null;
  const plan = PLANS[me.user.plan];
  return (
    <>
      <PageHead title="Minha conta" sub={me.user.email} />
      {params.get("assinatura") === "ok" && <div className="alert info" style={{ marginBottom: 16 }}>Assinatura confirmada. Bom proveito!</div>}
      <div className="grid cols-2">
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Plano {plan.name}</h3>
          <div className="muted small">
            {me.user.plan === "free"
              ? "Plano gratuito."
              : `${me.user.planPeriod === "annual" ? "Anual" : "Mensal"} · ${
                  me.user.planStatus === "active" ? "ativo" : me.user.planStatus === "past_due" ? "pagamento pendente" : "cancelado"
                }${me.user.planRenewsAt ? ` · renova em ${date(me.user.planRenewsAt)}` : ""}`}
          </div>
          <Meter label="Vídeos este mês" used={me.usage.videos} limit={me.limits.videosPerMonth} />
          <Meter label="Roteiros este mês" used={me.usage.scripts} limit={me.limits.scriptsPerMonth} />
          <ErrorBox error={error} />
          <div className="row">
            <Link to="/planos" className="btn primary sm">
              Mudar de plano
            </Link>
            {me.user.hasBilling && (
              <button
                className="btn sm"
                onClick={async () => {
                  try {
                    const { url } = await api<{ url: string }>("/api/billing/portal", { body: {} });
                    window.location.href = url;
                  } catch (err) {
                    setError(err);
                  }
                }}
              >
                Pagamentos e cancelamento
              </button>
            )}
          </div>
        </div>
        <div className="card stack">
          <h3 style={{ margin: 0 }}>Sessão</h3>
          <p className="muted small" style={{ margin: 0 }}>
            Garantia de 7 dias: se não gostou, fale com a gente pelo suporte e devolvemos 100% do valor.
          </p>
          <button className="btn sm" style={{ alignSelf: "flex-start" }} onClick={() => void logout()}>
            Sair
          </button>
        </div>
      </div>
    </>
  );
}

export function AdminPage() {
  const [csv, setCsv] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <PageHead title="Admin" sub="Importação de produtos (CSV). Para atualização automática, veja docs/DADOS.md." />
      <div className="card stack">
        <p className="muted small" style={{ margin: 0 }}>
          Colunas: external_id, country (BR/US), name, category, shop_name, image_url, product_url, price, commission_pct,
          sales_1d, sales_7d, sales_30d, gmv_1d, gmv_7d, gmv_30d, creators_count. Separador vírgula ou ponto e vírgula.
          Importar apaga os produtos de exemplo.
        </p>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (f) setCsv(await f.text());
          }}
        />
        <textarea value={csv} onChange={(e) => setCsv(e.target.value)} rows={8} placeholder="Ou cole o CSV aqui" />
        <ErrorBox error={error} />
        {msg && <div className="alert info">{msg}</div>}
        <button
          className="btn primary"
          style={{ alignSelf: "flex-start" }}
          disabled={!csv || busy}
          onClick={async () => {
            setBusy(true);
            setError(null);
            setMsg(null);
            try {
              const r = await api<{ imported: number }>("/api/admin/products/import", { body: { csv } });
              setMsg(`${r.imported} produtos importados.`);
            } catch (err) {
              setError(err);
            } finally {
              setBusy(false);
            }
          }}
        >
          Importar
        </button>
      </div>
    </>
  );
}
