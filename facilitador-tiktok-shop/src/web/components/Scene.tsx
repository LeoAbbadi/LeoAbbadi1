// Cenas desenhadas em SVG no lugar de fotografia: a paisagem do topo (com parallax)
// e a arte dos cartões de vídeo/produto. Leves, nítidas em qualquer tela e sem
// depender de banco de imagens.
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";

export function HeroScene() {
  const reduce = useReducedMotion();
  const { scrollY } = useScroll();
  const far = useTransform(scrollY, [0, 900], [0, reduce ? 0 : 60]);
  const mid = useTransform(scrollY, [0, 900], [0, reduce ? 0 : 140]);
  const near = useTransform(scrollY, [0, 900], [0, reduce ? 0 : 240]);
  const sun = useTransform(scrollY, [0, 900], [0, reduce ? 0 : 90]);

  return (
    <svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice" aria-hidden>
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#04121a" />
          <stop offset="0.38" stopColor="#0d3140" />
          <stop offset="0.52" stopColor="#3b5560" />
          <stop offset="0.6" stopColor="#d88c5c" />
          <stop offset="0.64" stopColor="#f2b27a" />
        </linearGradient>
        <radialGradient id="sunGlow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#fff1d6" stopOpacity="1" />
          <stop offset="0.18" stopColor="#ffcf96" stopOpacity="0.85" />
          <stop offset="0.5" stopColor="#ff9e62" stopOpacity="0.25" />
          <stop offset="1" stopColor="#ff9e62" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#3d7f86" />
          <stop offset="0.25" stopColor="#0f6f78" />
          <stop offset="0.6" stopColor="#0a5560" />
          <stop offset="1" stopColor="#04262d" />
        </linearGradient>
        <linearGradient id="reflect" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffd8a8" stopOpacity="0.9" />
          <stop offset="1" stopColor="#ffd8a8" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="cliffFar" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#24505a" />
          <stop offset="1" stopColor="#13343b" />
        </linearGradient>
        <linearGradient id="cliffMid" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2e5e4a" />
          <stop offset="0.5" stopColor="#173a33" />
          <stop offset="1" stopColor="#0b221f" />
        </linearGradient>
        <linearGradient id="cliffNear" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#21473b" />
          <stop offset="1" stopColor="#06130f" />
        </linearGradient>
        <linearGradient id="sand" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#e7cfa4" stopOpacity="0" />
          <stop offset="0.5" stopColor="#e7cfa4" stopOpacity="0.85" />
          <stop offset="1" stopColor="#e7cfa4" stopOpacity="0.2" />
        </linearGradient>
        <filter id="blur8"><feGaussianBlur stdDeviation="8" /></filter>
        <filter id="blur20"><feGaussianBlur stdDeviation="20" /></filter>
        <filter id="rock" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="3" seed="4" result="n" />
          <feColorMatrix in="n" type="saturate" values="0" result="g" />
          <feComponentTransfer in="g" result="g2"><feFuncA type="linear" slope="0.35" /></feComponentTransfer>
          <feComposite in="g2" in2="SourceGraphic" operator="in" result="tex" />
          <feBlend in="SourceGraphic" in2="tex" mode="multiply" />
        </filter>
      </defs>

      <rect width="1600" height="1000" fill="url(#sky)" />

      {/* sol e nuvens */}
      <motion.g style={{ y: sun }}>
        <circle cx="800" cy="610" r="380" fill="url(#sunGlow)">
          <animate attributeName="r" values="370;400;370" dur="9s" repeatCount="indefinite" />
        </circle>
        <g filter="url(#blur20)" opacity="0.8">
          <ellipse cx="560" cy="430" rx="260" ry="36" fill="#f6c79a" opacity="0.45">
            <animate attributeName="cx" values="540;600;540" dur="40s" repeatCount="indefinite" />
          </ellipse>
          <ellipse cx="1040" cy="380" rx="300" ry="42" fill="#c9a3a0" opacity="0.35">
            <animate attributeName="cx" values="1060;980;1060" dur="52s" repeatCount="indefinite" />
          </ellipse>
          <ellipse cx="300" cy="250" rx="320" ry="50" fill="#5d7f8c" opacity="0.4" />
          <ellipse cx="1300" cy="200" rx="260" ry="40" fill="#58798a" opacity="0.35" />
        </g>
      </motion.g>

      {/* mar */}
      <rect y="620" width="1600" height="380" fill="url(#sea)" />
      <rect x="760" y="620" width="80" height="300" fill="url(#reflect)" filter="url(#blur8)" opacity="0.75">
        <animate attributeName="opacity" values="0.55;0.9;0.55" dur="4s" repeatCount="indefinite" />
      </rect>
      <g stroke="#bff3ea" strokeLinecap="round" opacity="0.35">
        {Array.from({ length: 22 }, (_, i) => {
          const y = 640 + i * 16 + (i % 3) * 3;
          const w = 40 + ((i * 37) % 120);
          const x = (i * 211) % 1500;
          return (
            <line key={i} x1={x} x2={x + w} y1={y} y2={y} strokeWidth={1 + i * 0.08} strokeDasharray="22 14">
              <animate attributeName="stroke-dashoffset" values="0;-72" dur={`${4 + (i % 5)}s`} repeatCount="indefinite" />
            </line>
          );
        })}
      </g>

      {/* ilhas distantes */}
      <motion.g style={{ y: far }} filter="url(#rock)">
        <path d="M0 640 L0 590 C60 570 120 585 170 600 C230 615 300 628 360 640 Z" fill="url(#cliffFar)" opacity="0.9" />
        <path d="M1180 640 C1200 600 1240 560 1290 548 C1340 536 1400 552 1460 560 C1520 568 1570 575 1600 580 L1600 640 Z" fill="url(#cliffFar)" />
        <path d="M640 640 C650 600 690 580 720 585 C750 590 768 615 774 640 Z" fill="#1b4148" />
      </motion.g>

      {/* rocha no mar (como a da referência) */}
      <motion.g style={{ y: mid }} filter="url(#rock)">
        <path d="M480 700 C470 640 490 590 530 560 C570 535 620 540 650 570 C680 600 690 650 690 700 Z" fill="url(#cliffMid)" />
        <path d="M500 600 C520 575 560 560 600 566 C620 570 640 585 650 600 C610 590 560 590 500 600 Z" fill="#3f7a55" opacity="0.8" />
        <ellipse cx="585" cy="702" rx="130" ry="10" fill="#d8fff6" opacity="0.25">
          <animate attributeName="rx" values="120;140;120" dur="5s" repeatCount="indefinite" />
        </ellipse>
      </motion.g>

      {/* penhascos da direita */}
      <motion.g style={{ y: mid }} filter="url(#rock)">
        <path d="M1050 1000 C1060 860 1080 720 1120 640 C1150 580 1150 480 1190 420 C1230 360 1290 330 1340 345 C1380 300 1450 260 1520 270 C1560 275 1590 290 1600 300 L1600 1000 Z" fill="url(#cliffMid)" />
        <path d="M1140 600 C1170 520 1200 450 1250 410 C1300 370 1360 360 1420 330 C1470 305 1540 300 1600 320 L1600 380 C1530 370 1460 390 1400 420 C1330 455 1260 470 1210 520 C1180 550 1160 580 1140 600 Z" fill="#3c7650" opacity="0.75" />
        <path d="M1110 1000 C1140 900 1190 820 1260 760 C1310 720 1360 690 1400 640 L1420 1000 Z" fill="url(#sand)" opacity="0.55" />
      </motion.g>

      {/* espuma das ondas na praia */}
      <g fill="none" stroke="#e8fffb" strokeWidth="3" strokeLinecap="round" opacity="0.6">
        <path d="M1060 900 C1110 860 1160 830 1230 790">
          <animate attributeName="stroke-dasharray" values="0 400;300 400;0 400" dur="6s" repeatCount="indefinite" />
        </path>
        <path d="M1000 960 C1060 920 1120 890 1180 860" opacity="0.6">
          <animate attributeName="stroke-dasharray" values="0 400;260 400;0 400" dur="7.5s" repeatCount="indefinite" />
        </path>
      </g>

      {/* primeiro plano */}
      <motion.g style={{ y: near }} filter="url(#rock)">
        <path d="M700 1000 C720 930 760 870 800 840 C830 815 870 800 900 820 C940 845 960 900 980 1000 Z" fill="url(#cliffNear)" />
        <path d="M760 880 C790 850 830 830 870 835 C900 840 920 860 930 880 C880 868 820 868 760 880 Z" fill="#2c5e45" opacity="0.8" />
      </motion.g>

      {/* névoa */}
      <rect y="560" width="1600" height="120" fill="#cfe9ec" opacity="0.08" filter="url(#blur20)" />
    </svg>
  );
}

// ---------- arte dos cartões ----------

export const THEMES = [
  { a: "#0e6b6b", b: "#05262b", glow: "#7af2d6" }, // verde-água
  { a: "#c46a3f", b: "#2a0f12", glow: "#ffc38f" }, // pôr do sol
  { a: "#4b3fa6", b: "#120c2c", glow: "#b8a8ff" }, // estúdio neon
  { a: "#1d5f9a", b: "#061a2e", glow: "#8fd0ff" }, // oceano
  { a: "#a03a6a", b: "#22081a", glow: "#ff9cc8" }, // rosa
  { a: "#3f7a3a", b: "#0b1f0c", glow: "#c3f59a" }, // floresta
] as const;

/** Fundo de "vídeo" de produto: estúdio com luz, pedestal e o produto flutuando. */
export function ProductArt({ theme = 0, emoji, seed = 0 }: { theme?: number; emoji: string; seed?: number }) {
  const t = THEMES[theme % THEMES.length]!;
  const id = `pa-${theme}-${seed}`;
  return (
    <div className="art" style={{ background: `radial-gradient(120% 80% at 30% 10%, ${t.a}, ${t.b} 70%)` }}>
      <svg viewBox="0 0 200 356" preserveAspectRatio="xMidYMid slice" width="100%" height="100%" aria-hidden>
        <defs>
          <radialGradient id={`${id}-l`} cx="0.5" cy="0" r="1">
            <stop offset="0" stopColor={t.glow} stopOpacity="0.55" />
            <stop offset="0.6" stopColor={t.glow} stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`${id}-p`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#ffffff" stopOpacity="0.28" />
            <stop offset="1" stopColor="#ffffff" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <path d="M60 0 L140 0 L200 260 L0 260 Z" fill={`url(#${id}-l)`} />
        <ellipse cx="100" cy="262" rx="70" ry="14" fill={`url(#${id}-p)`} />
        <rect x="30" y="262" width="140" height="94" fill="#000" opacity="0.25" />
        {Array.from({ length: 10 }, (_, i) => (
          <circle key={i} cx={(i * 47 + seed * 13) % 200} cy={(i * 83 + seed * 29) % 240} r={0.8 + (i % 3) * 0.5} fill="#fff" opacity="0.5">
            <animate attributeName="opacity" values="0.1;0.7;0.1" dur={`${2 + (i % 4)}s`} begin={`${i * 0.3}s`} repeatCount="indefinite" />
          </circle>
        ))}
      </svg>
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "52%",
          fontSize: "clamp(56px, 30cqw, 120px)",
          transform: "translate(-50%, -60%)",
          filter: `drop-shadow(0 18px 24px rgba(0,0,0,.55)) drop-shadow(0 0 30px ${t.glow}55)`,
          animation: `float 5s ease-in-out ${seed * 0.4}s infinite`,
        }}
      >
        {emoji}
      </div>
    </div>
  );
}
