export const brl = (cents: number | string) =>
  (Number(cents) / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

export function compactBRL(cents: number | string): string {
  const v = Number(cents) / 100;
  if (v >= 1_000_000) return `R$ ${(v / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (v >= 1_000) return `R$ ${(v / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return brl(cents);
}

export const num = (n: number) => n.toLocaleString("pt-BR");

export function compactNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (n >= 1_000) return `${(n / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return num(n);
}

export function bytes(n: number | null): string {
  if (!n) return "";
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} GB`;
  return `${Math.round(n / 1024 ** 2)} MB`;
}

export function date(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export function weekday(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR", { weekday: "short" }).replace(".", "");
}

export function today(): string {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}
