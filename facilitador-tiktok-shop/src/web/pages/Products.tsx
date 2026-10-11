import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, ApiError, type Product } from "../api.ts";
import { ErrorBox, Loading, PageHead, useLoad } from "../components/ui.tsx";
import { useSession } from "../session.tsx";
import { brl, compactBRL, compactNum, date, num } from "../format.ts";

type Period = "1d" | "7d" | "30d";
type Sort = "gmv" | "sales" | "growth";

export function Growth({ value }: { value: number }) {
  return <span className={value >= 0 ? "growth-up" : "growth-down"}>{value >= 0 ? "+" : ""}{Math.round(value)}%</span>;
}

export function Thumb({ p }: { p: { name: string; image_url: string } }) {
  return <div className="thumb">{p.image_url ? <img src={p.image_url} alt="" loading="lazy" /> : p.name.slice(0, 1)}</div>;
}

export function ProductsPage() {
  const { me } = useSession();
  const navigate = useNavigate();
  const [country, setCountry] = useState<"BR" | "US">("BR");
  const [period, setPeriod] = useState<Period>("7d");
  const [sort, setSort] = useState<Sort>("gmv");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const categories = useLoad(() => api<string[]>("/api/products/categories"), []);
  const params = new URLSearchParams({ country, period, sort, limit: "50" });
  if (category) params.set("category", category);
  if (search) params.set("q", search);
  const { data, error, loading } = useLoad(
    () => api<{ items: Product[]; locked: boolean }>(`/api/products?${params}`),
    [params.toString()],
  );
  const usLocked = !me?.limits.countries.includes("US");
  const sample = data?.items.some((p) => p.is_sample);

  return (
    <>
      <PageHead title="Produtos em alta" sub="O que está vendendo no TikTok Shop, por faturamento estimado." />
      {sample && (
        <div className="alert warn small" style={{ marginBottom: 16 }}>
          Mostrando <strong>dados de exemplo</strong>. Conecte um provedor de dados ou importe um CSV na área Admin para ver
          produtos reais (veja docs/DADOS.md).
        </div>
      )}
      <div className="card row" style={{ marginBottom: 16, gap: 10 }}>
        <div className="toggle">
          <button className={country === "BR" ? "on" : ""} onClick={() => setCountry("BR")}>
            🇧🇷 Brasil
          </button>
          <button className={country === "US" ? "on" : ""} onClick={() => !usLocked && setCountry("US")} title={usLocked ? "Plano Pro" : ""}>
            🇺🇸 EUA {usLocked && "🔒"}
          </button>
        </div>
        <select value={period} onChange={(e) => setPeriod(e.target.value as Period)} style={{ width: "auto" }}>
          <option value="1d">Últimas 24h</option>
          <option value="7d">Últimos 7 dias</option>
          <option value="30d">Últimos 30 dias</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value as Sort)} style={{ width: "auto" }}>
          <option value="gmv">Mais faturamento</option>
          <option value="sales">Mais vendas</option>
          <option value="growth">Explodindo (24h)</option>
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ width: "auto" }}>
          <option value="">Todas as categorias</option>
          {categories.data?.map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <form
          className="row spacer"
          onSubmit={(e) => {
            e.preventDefault();
            setSearch(q);
          }}
        >
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar produto ou loja" style={{ flex: 1, minWidth: 160 }} />
        </form>
      </div>
      <ErrorBox error={error} />
      {loading ? (
        <Loading />
      ) : (
        <div className="card table-wrap" style={{ padding: 0 }}>
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Produto</th>
                <th>Faturamento</th>
                <th>Vendas</th>
                <th>24h</th>
                <th>Preço</th>
                <th>Comissão</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((p, i) => (
                <tr key={p.id} className="clickable" onClick={() => navigate(`/app/produtos/${p.id}`)}>
                  <td className="muted">{i + 1}</td>
                  <td>
                    <div className="row" style={{ flexWrap: "nowrap" }}>
                      <Thumb p={p} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 600 }}>
                          {p.favorite && "★ "}
                          {p.name}
                        </div>
                        <div className="faint small">
                          {p.category} · {p.shop_name}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <strong>{compactBRL(p.gmv_cents)}</strong>
                  </td>
                  <td>{compactNum(p.sales)}</td>
                  <td>
                    <Growth value={p.growth_pct_1d} />
                  </td>
                  <td>{brl(p.price_cents)}</td>
                  <td>{p.commission_pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.locked && (
            <div className="empty">
              No plano grátis você vê o top 10. <Link to="/planos">Assine para ver o ranking completo</Link>.
            </div>
          )}
          {data && !data.items.length && !data.locked && <div className="empty">Nenhum produto encontrado.</div>}
        </div>
      )}
    </>
  );
}

interface ProductDetailData {
  product: Product & {
    country: string;
    sales_1d: number;
    sales_7d: number;
    sales_30d: number;
    gmv_cents_1d: string;
    gmv_cents_7d: string;
    gmv_cents_30d: string;
  };
  videos: { creator_handle: string; video_url: string; views: string; gmv_cents: string; posted_at: string | null }[];
}

export function ProductPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, setData } = useLoad(() => api<ProductDetailData>(`/api/products/${id}`), [id]);
  if (loading) return <Loading />;
  if (!data) {
    return error instanceof ApiError && error.status === 402 ? (
      <div className="alert warn">
        {error.message} <Link to="/planos">Ver planos</Link>
      </div>
    ) : (
      <ErrorBox error={error} />
    );
  }
  const p = data.product;
  async function toggleFavorite() {
    await api(`/api/favorites/${p.id}`, { method: p.favorite ? "DELETE" : "PUT" });
    setData({ ...data!, product: { ...p, favorite: !p.favorite } });
  }
  return (
    <>
      <PageHead
        title={p.name}
        sub={`${p.category} · ${p.shop_name} · ${p.country === "US" ? "EUA" : "Brasil"}`}
        actions={
          <>
            <button className="btn" onClick={toggleFavorite}>
              {p.favorite ? "★ Favorito" : "☆ Favoritar"}
            </button>
            {p.product_url && (
              <a className="btn" href={p.product_url} target="_blank" rel="noreferrer">
                Ver no TikTok Shop
              </a>
            )}
            <button className="btn primary" onClick={() => navigate(`/app/roteiros?produto=${encodeURIComponent(p.name)}`)}>
              Criar roteiro
            </button>
          </>
        }
      />
      {p.is_sample && <div className="alert warn small" style={{ marginBottom: 16 }}>Produto de exemplo, com números fictícios.</div>}
      <div className="grid cols-4" style={{ marginBottom: 16 }}>
        {[
          ["Faturamento 24h", compactBRL(p.gmv_cents_1d)],
          ["Faturamento 7 dias", compactBRL(p.gmv_cents_7d)],
          ["Faturamento 30 dias", compactBRL(p.gmv_cents_30d)],
          ["Vendas 7 dias", num(p.sales_7d)],
          ["Preço", brl(p.price_cents)],
          ["Comissão", `${p.commission_pct}%`],
          ["Criadores vendendo", num(p.creators_count)],
          ["Atualizado em", date(p.updated_at)],
        ].map(([k, v]) => (
          <div className="card stat" key={k}>
            <span className="k">{k}</span>
            <span className="v">{v}</span>
          </div>
        ))}
      </div>
      <div className="card stack">
        <div className="row between">
          <h3 style={{ margin: 0 }}>Ritmo das vendas</h3>
          <span>
            Últimas 24h vs. média da semana: <Growth value={p.growth_pct_1d} />
          </span>
        </div>
        <p className="muted small" style={{ margin: 0 }}>
          Comissão estimada por venda: <strong>{brl((p.price_cents * p.commission_pct) / 100)}</strong>. Com 1% das vendas
          da última semana você faria cerca de{" "}
          <strong>{brl(((p.price_cents * p.commission_pct) / 100) * Math.round(p.sales_7d * 0.01))}</strong> em comissão.
        </p>
      </div>
      <div className="card" style={{ marginTop: 16 }}>
        <h3>Vídeos que mais venderam</h3>
        {data.videos.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Criador</th>
                <th>Visualizações</th>
                <th>Faturamento</th>
                <th>Postado</th>
              </tr>
            </thead>
            <tbody>
              {data.videos.map((v, i) => (
                <tr key={i}>
                  <td>{v.video_url ? <a href={v.video_url} target="_blank" rel="noreferrer">{v.creator_handle}</a> : v.creator_handle}</td>
                  <td>{compactNum(Number(v.views))}</td>
                  <td>{compactBRL(v.gmv_cents)}</td>
                  <td className="muted">{v.posted_at ? date(v.posted_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Sem vídeos registrados.</p>
        )}
      </div>
    </>
  );
}
