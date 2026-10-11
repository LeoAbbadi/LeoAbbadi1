// Ícones de traço (24x24), no estilo dos ícones da referência.
const base = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;
type P = { size?: number };

export const Icon = {
  Arrow: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base} className="arrow"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
  ),
  ArrowLeft: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
  ),
  Play: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" /></svg>
  ),
  Search: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
  ),
  Layers: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></svg>
  ),
  Trend: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M3 17 9 11l4 4 8-8" /><path d="M15 7h6v6" /></svg>
  ),
  Pen: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z" /><path d="m13.5 6.5 4 4" /></svg>
  ),
  Grid: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><rect x="3.5" y="3.5" width="7" height="7" rx="2" /><rect x="13.5" y="3.5" width="7" height="7" rx="2" /><rect x="3.5" y="13.5" width="7" height="7" rx="2" /><rect x="13.5" y="13.5" width="7" height="7" rx="2" /></svg>
  ),
  User: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
  ),
  Gear: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
  ),
  Shield: ({ size = 30 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6z" /><path d="m8.8 12 2.2 2.2 4.2-4.4" /></svg>
  ),
  Calendar: ({ size = 30 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 10h17M8 3v4M16 3v4" /></svg>
  ),
  Wave: ({ size = 30 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M4 10v4M8 7v10M12 4v16M16 8v8M20 11v2" /></svg>
  ),
  Lock: ({ size = 30 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><rect x="4.5" y="10.5" width="15" height="10" rx="2.5" /><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" /><circle cx="12" cy="15.5" r="1.2" /></svg>
  ),
  Order: ({ size = 30 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 5.5h1.2v3M4 11.2c.6-.6 1.8-.5 1.8.4 0 .8-1.8 1.4-1.8 2.4h1.9M4 17h1.6c.4 0 .6.4.4.7l-.8.6.8.6c.2.3 0 .7-.4.7H4" /></svg>
  ),
  Cart: ({ size = 16 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M3 4h2l2.4 11h10.2L20 7.5H6.2" /><circle cx="9" cy="19.5" r="1.4" /><circle cx="17" cy="19.5" r="1.4" /></svg>
  ),
  Spark: ({ size = 18 }: P) => (
    <svg width={size} height={size} viewBox="0 0 24 24" {...base}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" /></svg>
  ),
};

export function LogoMark({ size = 38 }: P) {
  // montanha/play estilizado: três camadas como gancho, corpo e CTA
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      <defs>
        <linearGradient id="lm" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#a8fbe5" />
          <stop offset="1" stopColor="#2fc9a3" />
        </linearGradient>
      </defs>
      <path d="M4 32 15 12l7 12" fill="none" stroke="url(#lm)" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      <path d="M15 32 25 14l11 18z" fill="none" stroke="url(#lm)" strokeWidth="2.4" strokeLinejoin="round" />
      <path d="M23.5 25.5v3.6l3-1.8z" fill="#a8fbe5" />
    </svg>
  );
}
