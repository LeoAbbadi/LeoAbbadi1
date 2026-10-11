// Efeitos visuais compartilhados: vidro líquido, brilho que segue o cursor,
// textos que surgem, contadores animados e o fundo "aurora".
import { useEffect, useRef, useState, type ReactNode } from "react";
import { animate, motion, useInView, useReducedMotion } from "motion/react";

export const EASE = [0.22, 1, 0.36, 1] as const;

/** Filtros SVG usados pelo CSS (backdrop-filter: url(#liquid-glass)). Renderize uma vez. */
export function LiquidGlassDefs() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden focusable="false">
      <defs>
        <filter id="liquid-glass" x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.008 0.012" numOctaves="2" seed="7" result="noise" />
          <feGaussianBlur in="noise" stdDeviation="2.5" result="soft" />
          <feDisplacementMap in="SourceGraphic" in2="soft" scale="38" xChannelSelector="R" yChannelSelector="G" />
        </filter>
        <filter id="liquid-glass-soft" x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
          <feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="1" seed="3" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="14" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </defs>
    </svg>
  );
}

const GLOW_SELECTOR = ".glass, .card, .btn, .dropzone";

/** Atualiza --mx/--my no elemento de vidro sob o cursor (brilho especular). */
export function usePointerGlow() {
  useEffect(() => {
    // Refração real só no Chromium (Safari/Firefox ficam com o desfoque)
    const brands = (navigator as Navigator & { userAgentData?: { brands: { brand: string }[] } }).userAgentData?.brands;
    if (brands?.some((b) => /Chromium/i.test(b.brand))) document.documentElement.classList.add("lg-refract");

    let frame = 0;
    const onMove = (e: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const el = (e.target as Element | null)?.closest?.(GLOW_SELECTOR) as HTMLElement | null;
        if (!el) return;
        const r = el.getBoundingClientRect();
        el.style.setProperty("--mx", `${e.clientX - r.left}px`);
        el.style.setProperty("--my", `${e.clientY - r.top}px`);
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);
}

export function Aurora() {
  return (
    <>
      <div className="aurora" aria-hidden>
        <span />
        <span />
        <span />
        <span />
      </div>
      <div className="grain" aria-hidden />
    </>
  );
}

/** Surge ao entrar na tela (sobe + desfoque → nítido). */
export function Reveal({
  children,
  delay = 0,
  y = 28,
  className,
  style,
  as = "div",
}: {
  children: ReactNode;
  delay?: number;
  y?: number;
  className?: string;
  style?: React.CSSProperties;
  as?: "div" | "section" | "li";
}) {
  const reduce = useReducedMotion();
  const Tag = motion[as];
  return (
    <Tag
      className={className}
      style={style}
      initial={reduce ? false : { opacity: 0, y, filter: "blur(10px)" }}
      whileInView={{ opacity: 1, y: 0, filter: "blur(0px)" }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.9, delay, ease: EASE }}
    >
      {children}
    </Tag>
  );
}

/** Título que aparece palavra por palavra. */
export function SplitText({ text, delay = 0, className, stagger = 0.07 }: { text: string; delay?: number; className?: string; stagger?: number }) {
  const reduce = useReducedMotion();
  const words = text.split(" ");
  return (
    <span className={className} aria-label={text}>
      {words.map((w, i) => (
        <motion.span
          key={i}
          aria-hidden
          className="split-word"
          initial={reduce ? false : { opacity: 0, y: "0.45em", filter: "blur(12px)", rotateX: -40 }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)", rotateX: 0 }}
          transition={{ duration: 1, delay: delay + i * stagger, ease: EASE }}
          style={{ transformOrigin: "50% 100%" }}
        >
          {w}
          {i < words.length - 1 ? " " : ""}
        </motion.span>
      ))}
    </span>
  );
}

/** Número que conta até o valor quando aparece (ou quando o valor muda). */
export function Counter({ value, prefix = "", suffix = "", duration = 1.4 }: { value: number; prefix?: string; suffix?: string; duration?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const shown = useRef(0);
  const [text, setText] = useState(`${prefix}0${suffix}`);
  useEffect(() => {
    if (!inView) return;
    const controls = animate(shown.current, value, {
      duration,
      ease: EASE,
      onUpdate: (v) => {
        shown.current = v;
        setText(`${prefix}${Math.round(v).toLocaleString("pt-BR")}${suffix}`);
      },
    });
    return () => controls.stop();
  }, [inView, value, prefix, suffix, duration]);
  return <span ref={ref}>{text}</span>;
}

/** Inclina levemente o cartão na direção do cursor (efeito 3D). */
export function Tilt({ children, className, max = 8, style }: { children: ReactNode; className?: string; max?: number; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ ...style, transformStyle: "preserve-3d", transformPerspective: 900 }}
      onPointerMove={(e) => {
        if (reduce || !ref.current) return;
        const r = ref.current.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        ref.current.style.transform = `perspective(900px) rotateY(${x * max}deg) rotateX(${-y * max}deg)`;
      }}
      onPointerLeave={() => {
        if (ref.current) ref.current.style.transform = "";
      }}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
    >
      {children}
    </motion.div>
  );
}
