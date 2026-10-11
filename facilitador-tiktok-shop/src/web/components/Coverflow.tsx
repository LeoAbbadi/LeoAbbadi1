// Carrossel 3D de vídeos (inspirado na referência "Voyage"): o vídeo do centro
// fica de frente e os vizinhos giram em perspectiva. Avança sozinho, aceita
// arrastar, setas do teclado e clique.
import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { EASE } from "./fx.tsx";
import { Icon } from "./Icons.tsx";
import { ProductArt } from "./Scene.tsx";
import { LABEL_INFO, type OriginalityLabel } from "../../shared/combos.ts";

export interface CoverItem {
  emoji: string;
  theme: number;
  product: string;
  price: string;
  hook: string;
  combo: string;
  label: OriginalityLabel;
  views: string;
}

export const COVER_ITEMS: CoverItem[] = [
  { emoji: "💆‍♀️", theme: 1, product: "Escova secadora 3 em 1", price: "R$ 89", hook: "Ninguém me contou isso antes de eu comprar…", combo: "Gancho 3 + Corpo 1 + CTA 2", label: "original", views: "1,2 mi" },
  { emoji: "🎧", theme: 2, product: "Fone com cancelamento de ruído", price: "R$ 129", hook: "Testei no metrô lotado. Olha isso.", combo: "Gancho 7 + Corpo 4 + CTA 1", label: "original", views: "864 mil" },
  { emoji: "🧴", theme: 0, product: "Sérum vitamina C", price: "R$ 59", hook: "30 dias usando só isso no rosto", combo: "Gancho 1 + Corpo 2 + CTA 3", label: "original", views: "2,4 mi" },
  { emoji: "👟", theme: 3, product: "Tênis de corrida leve", price: "R$ 179", hook: "Parece caro, mas custou menos que um jantar", combo: "Gancho 5 + Corpo 3 + CTA 1", label: "variacao", views: "530 mil" },
  { emoji: "☕", theme: 5, product: "Mini processador recarregável", price: "R$ 74", hook: "Minha cozinha antes e depois disso", combo: "Gancho 9 + Corpo 5 + CTA 2", label: "original", views: "1,7 mi" },
  { emoji: "💄", theme: 4, product: "Kit maquiagem 5 em 1", price: "R$ 49", hook: "3 erros que todo mundo comete na make", combo: "Gancho 2 + Corpo 1 + CTA 3", label: "variacao", views: "940 mil" },
];

export function Coverflow({ items = COVER_ITEMS, interval = 3400 }: { items?: CoverItem[]; interval?: number }) {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const reduce = useReducedMotion();
  const n = items.length;
  const go = useCallback((d: number) => setActive((a) => (a + d + n) % n), [n]);

  useEffect(() => {
    if (paused || reduce) return;
    const t = setInterval(() => go(1), interval);
    return () => clearInterval(t);
  }, [paused, reduce, go, interval]);

  const cur = items[active]!;
  return (
    <div
      className="coverflow"
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") go(1);
        if (e.key === "ArrowLeft") go(-1);
      }}
      tabIndex={0}
      role="region"
      aria-roledescription="carrossel"
      aria-label="Exemplos de vídeos gerados"
    >
      <motion.div
        className="stage"
        drag="x"
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.18}
        onDragEnd={(_, info) => {
          if (info.offset.x < -50) go(1);
          else if (info.offset.x > 50) go(-1);
        }}
      >
        {items.map((it, i) => {
          let d = i - active;
          if (d > n / 2) d -= n;
          if (d < -n / 2) d += n;
          const abs = Math.abs(d);
          return (
            <motion.div
              key={i}
              className="vcard"
              onClick={() => (d === 0 ? undefined : go(d))}
              animate={{
                x: d * 250,
                z: -abs * 180,
                rotateY: d === 0 ? 0 : d > 0 ? -32 : 32,
                scale: d === 0 ? 1 : 0.86,
                opacity: abs > 2 ? 0 : 1,
                filter: d === 0 ? "brightness(1)" : "brightness(0.55)",
              }}
              transition={{ duration: reduce ? 0 : 0.9, ease: EASE }}
              style={{ zIndex: 10 - abs }}
            >
              <ProductArt theme={it.theme} emoji={it.emoji} seed={i} />
              <div className="ui">
                <div className="row between">
                  <span className={`pill ${it.label}`}>{LABEL_INFO[it.label].title}</span>
                  <span className="small" style={{ fontWeight: 700 }}>▶ {it.views}</span>
                </div>
                <div className="stack" style={{ gap: 10 }}>
                  <div className="caption">{it.hook}</div>
                  <div className="cart">
                    <Icon.Cart /> {it.product} · {it.price}
                  </div>
                  <div className="bar">
                    <motion.div
                      key={d === 0 ? `on-${active}` : "off"}
                      initial={{ width: "0%" }}
                      animate={{ width: d === 0 && !paused ? "100%" : "0%" }}
                      transition={{ duration: d === 0 && !paused ? interval / 1000 : 0.2, ease: "linear" }}
                    />
                  </div>
                </div>
              </div>
              <div className="side" aria-hidden>
                <i>♥</i>
                <i>💬</i>
                <i>↗</i>
              </div>
            </motion.div>
          );
        })}
      </motion.div>

      <div className="cover-title">
        <AnimatePresence mode="wait">
          <motion.div
            key={active}
            initial={{ opacity: 0, y: 24, filter: "blur(12px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -18, filter: "blur(10px)" }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <div className="t">{cur.combo}</div>
            <div className="rule" />
            <div className="muted">Mesmo produto, vídeo novo. Gravado uma vez só.</div>
          </motion.div>
        </AnimatePresence>
      </div>

      <button className="btn icon rail-arrow l" style={{ left: "4%" }} onClick={() => go(-1)} aria-label="Anterior">
        <Icon.ArrowLeft />
      </button>
      <button className="btn icon rail-arrow r" style={{ right: "4%" }} onClick={() => go(1)} aria-label="Próximo">
        <Icon.Arrow />
      </button>
      <div className="cover-dots" style={{ position: "absolute", bottom: 14 }}>
        {items.map((_, i) => (
          <button key={i} className={i === active ? "on" : ""} onClick={() => setActive(i)} aria-label={`Vídeo ${i + 1}`} />
        ))}
      </div>
    </div>
  );
}
