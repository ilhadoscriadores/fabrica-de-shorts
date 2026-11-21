import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { FONTE } from "./fontes";
import type { SeloProps } from "./tipos";

// Selo da Fábrica de Shorts: a faixa da Ilha num quadro 1080x200 com fundo transparente.
// Entra por um lado, mostra 2 mensagens e sai pelo outro. O Python cola por cima do corte.
//   1) "Quer fazer cortes assim / no automático?"
//   2) "FEITO NA FÁBRICA DE SHORTS | [logo da ilha]"

export const SELO_QUADROS = 141; // 4,7 s a 30 fps

const DUR = 4.7; // segundos na tela, da entrada até sumir
const T_TROCA = 2.15; // quando a mensagem 1 vira a 2
const T_ROLA = 0.32; // duração da troca
const T_SAI = 0.42; // duração da saída
const LARGURA = 840;
const ALTURA = 150;
const TOPO = 25;

// Tesoura em SVG (emoji sai fino ou trocado no render)
const Tesoura: React.FC<{ cor: string; tinta: string }> = ({ cor, tinta }) => (
  <div style={{ width: 76, height: 76, borderRadius: 18, background: cor, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
    <svg width={46} height={46} viewBox="0 0 24 24" fill="none" stroke={tinta} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="6" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <line x1="20" y1="4" x2="8.12" y2="15.88" />
      <line x1="14.47" y1="14.48" x2="20" y2="20" />
      <line x1="8.12" y1="8.12" x2="12" y2="12" />
    </svg>
  </div>
);

// Cor clara (amarelo, dourado...) pede tesoura escura
const claro = (hex: string) => {
  const n = parseInt(hex.replace("#", "").slice(0, 6), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 150;
};
const CL = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const INOUT = Easing.bezier(0.65, 0, 0.35, 1);

export const Selo: React.FC<SeloProps> = ({ lado, cor }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const t = frame / fps;
  if (t > DUR) return null;
  const tinta = claro(cor) ? "#111" : "#fff";

  // Entrada com mola, saída acelerando: a faixa "passa" pela tela.
  const ent = spring({ frame, fps, config: { damping: 17, stiffness: 150, mass: 0.7 } });
  const sai = interpolate(t, [DUR - T_SAI, DUR], [0, 1], { ...CL, easing: Easing.in(Easing.cubic) });
  const sinal = lado === "esq" ? -1 : 1;
  const x0 = (width - LARGURA) / 2;
  const longe = x0 + LARGURA + 60;
  const x = x0 + sinal * (1 - ent) * longe - sinal * sai * longe;
  const inclina = sinal * (1 - ent) * 7 - sinal * sai * 7;

  // Troca da mensagem 1 para a 2 (rola para cima)
  const p = interpolate(t, [T_TROCA, T_TROCA + T_ROLA], [0, 1], { ...CL, easing: INOUT });
  // Barrinha que enche enquanto a faixa está parada
  const barra = interpolate(t, [0.4, DUR - T_SAI], [0, 1], CL);

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: x,
          top: TOPO,
          width: LARGURA,
          height: ALTURA,
          transform: `skewX(${inclina}deg)`,
          borderRadius: 22,
          overflow: "hidden",
          background: "linear-gradient(180deg, rgba(24,24,28,0.95), rgba(6,6,8,0.95))",
          // sombra mais curta que a da faixa original: o quadro tem só 200 px de altura
          boxShadow: `0 10px 20px rgba(0,0,0,0.6), 0 0 0 2px ${cor}73`,
        }}
      >
        {/* Tarja do lado */}
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 12, background: cor }} />

        {/* Mensagem 1 */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            paddingLeft: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 22,
            transform: `translateY(${-p * ALTURA}px)`,
            opacity: 1 - p,
          }}
        >
          <Tesoura cor={cor} tinta={tinta} />
          <div style={{ fontFamily: FONTE, fontWeight: 800, fontSize: 48, lineHeight: 1.12, color: "#fff", letterSpacing: -0.5, whiteSpace: "nowrap" }}>
            <div>Quer fazer cortes assim</div>
            <div style={{ color: cor, fontWeight: 900 }}>no automático?</div>
          </div>
        </div>

        {/* Mensagem 2 */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            paddingLeft: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 28,
            transform: `translateY(${(1 - p) * ALTURA}px)`,
            opacity: p,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
            <div style={{ fontFamily: FONTE, fontWeight: 800, fontSize: 24, letterSpacing: 5, color: "rgba(255,255,255,0.72)" }}>FEITO NA</div>
            <div style={{ fontFamily: FONTE, fontWeight: 900, fontSize: 40, lineHeight: 1, color: "#fff", whiteSpace: "nowrap" }}>
              <div>FÁBRICA DE</div>
              <div>SHORTS</div>
            </div>
          </div>
          <div style={{ width: 2, height: 96, background: "rgba(255,255,255,0.18)" }} />
          <Img src={staticFile("ilha-logo.png")} style={{ height: 84 }} />
        </div>

        {/* Barrinha de tempo */}
        <div style={{ position: "absolute", left: 12, bottom: 0, height: 5, width: (LARGURA - 12) * barra, background: cor, opacity: 0.9 }} />
      </div>
    </AbsoluteFill>
  );
};
