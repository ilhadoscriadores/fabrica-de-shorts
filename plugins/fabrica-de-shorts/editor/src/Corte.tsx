import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  OffthreadVideo,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { caber, FONTE, medir } from "./fontes";
import type { Bloco, Caixa, Dados, Etiqueta, Imagem, Layout } from "./tipos";

// Corte 9:16 desenhado só a partir do dados.json (nada por vídeo aqui).

const VERMELHO = "#FF3B30";
const W = 1080;
const H = 1920;
const CL = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const limitar = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

const Ctx = React.createContext<Dados | null>(null);
const useD = () => React.useContext(Ctx)!;

// ---------- câmera: posição no quadro atual ----------
type Ponto = Dados["camera"][number];
const posCamera = (cam: Ponto[], frame: number) => {
  if (!cam.length) return { cx: 0.5, cy: 0.5 };
  // último ponto com f <= frame (dois no mesmo f: vale o de baixo = corte seco)
  let i = -1;
  for (let j = 0; j < cam.length; j++) if (cam[j].f <= frame) i = j;
  if (i < 0) return cam[0];
  if (i === cam.length - 1) return cam[i];
  const a = cam[i];
  const b = cam[i + 1];
  const p = (frame - a.f) / (b.f - a.f);
  return { cx: a.cx + (b.cx - a.cx) * p, cy: a.cy + (b.cy - a.cy) * p };
};

// ---------- live: webcam em cima, jogo embaixo ----------
const Painel: React.FC<{ src: string; bw: number; bh: number; caixa: Caixa; top: number; altura: number; foco: number; zoom: boolean }> = ({
  src, bw, bh, caixa, top, altura, foco, zoom,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const k = Math.max(W / caixa.w, altura / caixa.h); // a caixa cobre o painel inteiro
  const visivelW = W / k;
  const x0 = limitar(caixa.x + foco * caixa.w - visivelW / 2, caixa.x, caixa.x + caixa.w - visivelW);
  const y0 = caixa.y + (caixa.h - altura / k) / 2;
  const s = zoom ? 1.04 + 0.03 * Math.sin((2 * Math.PI * (frame / fps)) / 11 - Math.PI / 2) : 1;
  return (
    <div style={{ position: "absolute", left: 0, top, width: W, height: altura, overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, transform: `scale(${s})`, transformOrigin: "50% 50%" }}>
        <div style={{ position: "absolute", left: -x0 * k, top: -y0 * k, width: bw * k, height: bh * k }}>
          <OffthreadVideo src={src} volume={0} style={{ width: "100%", height: "100%" }} />
        </div>
      </div>
    </div>
  );
};

const FundoEmpilhado: React.FC<{ L: Layout }> = ({ L }) => {
  const D = useD();
  const src = staticFile(D.base.src);
  const hTop = Math.round(H * L.divisao);
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      {/* o som sai uma vez só, por este vídeo escondido */}
      <OffthreadVideo src={src} volume={1} style={{ position: "absolute", width: 2, height: 2, opacity: 0 }} />
      <Painel src={src} bw={D.base.largura} bh={D.base.altura} caixa={L.cam} top={0} altura={hTop} foco={L.foco_cam} zoom={false} />
      <Painel src={src} bw={D.base.largura} bh={D.base.altura} caixa={L.jogo} top={hTop} altura={H - hTop} foco={0.5} zoom={D.zoom} />
      <div style={{ position: "absolute", left: 0, top: hTop - 4, width: W, height: 8, background: D.cor }} />
    </AbsoluteFill>
  );
};

// ---------- fundo: vídeo recortado em 9:16 com zoom lento ----------
const Fundo: React.FC = () => {
  const D = useD();
  return D.layout ? <FundoEmpilhado L={D.layout} /> : <FundoRecortado />;
};

const FundoRecortado: React.FC = () => {
  const D = useD();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const cam = React.useMemo(() => [...D.camera].sort((a, b) => a.f - b.f), [D.camera]);
  const pos = posCamera(cam, frame);
  const cx = limitar(pos.cx, 0, 1);
  const cy = limitar(pos.cy, 0, 1);
  const k = Math.max(W / D.base.largura, H / D.base.altura);
  const vw = D.base.largura * k;
  const vh = D.base.altura * k;
  const left = limitar(W / 2 - cx * vw, W - vw, 0);
  const top = limitar(H / 2 - cy * vh, H - vh, 0);

  let transform: string | undefined;
  let transformOrigin: string | undefined;
  if (D.zoom) {
    // aproxima/afasta em ~5,5 s e desliza de leve, com o centro no rosto
    const t = frame / fps;
    const s = 1.06 + 0.045 * Math.sin((2 * Math.PI * t) / 11 - Math.PI / 2);
    const ox = cx * vw;
    const oy = cy * vh;
    // o deslize nunca mostra borda preta
    const x0 = left + ox * (1 - s);
    const x1 = left + ox + (vw - ox) * s;
    const dx = limitar(28 * Math.sin((2 * Math.PI * t) / 14), W - x1, -x0);
    transform = `translateX(${dx}px) scale(${s})`;
    transformOrigin = `${ox}px ${oy}px`;
  }

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "black" }}>
      <div style={{ position: "absolute", left, top, width: vw, height: vh, transform, transformOrigin }}>
        <OffthreadVideo src={staticFile(D.base.src)} volume={1} style={{ width: "100%", height: "100%" }} />
      </div>
      {/* leve vinheta para dar acabamento */}
      <AbsoluteFill
        style={{ background: "radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)" }}
      />
    </AbsoluteFill>
  );
};

// ---------- imagens ilustrativas ----------
const ImagemB: React.FC<{ b: Imagem; dur: number }> = ({ b, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = frame / dur;
  const fAbs = b.f0 + frame;
  const entra = spring({ frame, fps, config: { damping: 18, stiffness: 140 } });
  const sai = interpolate(frame, [dur - 5, dur], [1, 0], CL);
  const ease = Easing.inOut(Easing.sin)(Math.min(1, p));
  let scale = 1.0 + 0.1 * ease;
  let tx = 0;
  let ty = 0;
  if (b.movimento === "in-left") tx = -30 * ease;
  if (b.movimento === "in-right") tx = 30 * ease;
  if (b.movimento === "out") scale = 1.12 - 0.1 * ease;
  if (b.movimento === "up") {
    ty = -40 * ease;
    scale = 1.08;
  }

  // ---- efeito de entrada ----
  const tipo = b.entrada;
  let entradaScale = interpolate(entra, [0, 1], [1.12, 1]);
  let entradaX = 0;
  let blur = 0;
  let opac = Math.min(entra * 1.4, 1);
  if (tipo === "zoom") {
    entradaScale = interpolate(entra, [0, 1], [1.35, 1]);
    blur = interpolate(frame, [0, 8], [14, 0], CL);
  }
  if (tipo === "slide-esq" || tipo === "slide-dir") {
    const sl = spring({ frame, fps, config: { damping: 16, stiffness: 120, mass: 0.8 } });
    entradaX = (tipo === "slide-esq" ? -1 : 1) * (1 - sl) * W;
    entradaScale = 1;
    blur = interpolate(frame, [0, 6], [10, 0], CL);
    opac = 1;
  }
  const flash =
    tipo === "flash" ? interpolate(frame, [0, 2, 9], [0.95, 0.9, 0], CL) : interpolate(frame, [0, 5], [0.25, 0], CL);

  // ---- tremida (quadros absolutos) ----
  let shx = 0;
  let shy = 0;
  for (const tt of b.tremidas) {
    const d = fAbs - tt;
    if (d >= 0 && d < 12) {
      const a = 22 * (1 - d / 12);
      shx += a * Math.sin(d * 2.7);
      shy += a * Math.cos(d * 3.3);
    }
  }

  // ---- luz quente que atravessa na entrada ----
  const leak = interpolate(frame, [0, 22], [-40, 140], CL);
  const leakOp = interpolate(frame, [0, 6, 22], [0, 0.55, 0], CL);
  // ---- sirene ----
  const sir = b.sirene ? (Math.sin(frame / 3.2) + 1) / 2 : 0;

  return (
    <AbsoluteFill style={{ opacity: opac * sai, overflow: "hidden", transform: `translate(${entradaX + shx}px, ${shy}px)` }}>
      <Img
        src={staticFile(b.src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translate(${tx}px, ${ty}px) scale(${scale * entradaScale})`,
          filter: (b.sepia ? "sepia(0.75) contrast(1.05) brightness(0.95)" : "saturate(1.08) contrast(1.04)") + ` blur(${blur}px)`,
        }}
      />
      <AbsoluteFill
        style={{ background: "linear-gradient(180deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0) 30%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.55) 100%)" }}
      />
      <AbsoluteFill style={{ boxShadow: "inset 0 0 160px 30px rgba(0,0,0,0.55)" }} />
      {b.sirene && (
        <>
          <AbsoluteFill style={{ background: `radial-gradient(circle at 0% 20%, rgba(255,30,30,${0.38 * sir}), transparent 60%)`, mixBlendMode: "screen" }} />
          <AbsoluteFill style={{ background: `radial-gradient(circle at 100% 20%, rgba(40,90,255,${0.38 * (1 - sir)}), transparent 60%)`, mixBlendMode: "screen" }} />
        </>
      )}
      <AbsoluteFill
        style={{
          opacity: leakOp,
          mixBlendMode: "screen",
          background: `linear-gradient(110deg, transparent ${leak - 30}%, rgba(255,180,90,0.9) ${leak}%, transparent ${leak + 30}%)`,
        }}
      />
      <Grao forte={b.sepia} />
      {b.carimbo && <Carimbo text={b.carimbo} />}
      {flash > 0 && <AbsoluteFill style={{ background: "white", opacity: flash }} />}
    </AbsoluteFill>
  );
};

const Grao: React.FC<{ forte?: boolean }> = ({ forte }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill
      style={{
        opacity: forte ? 0.18 : 0.07,
        mixBlendMode: "overlay",
        backgroundImage:
          "repeating-radial-gradient(circle at " + ((frame * 37) % 100) + "% " + ((frame * 53) % 100) + "%, #fff 0 1px, transparent 1px 3px)",
      }}
    />
  );
};

const Carimbo: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 6, fps, config: { damping: 9, stiffness: 160 } });
  // texto longo encolhe para não sair da tela (Courier ~0,6 em por letra)
  const tam = Math.min(110, Math.floor(840 / Math.max(1, [...text].length * 0.66)));
  return (
    <div
      style={{
        position: "absolute",
        top: 260,
        right: 70,
        transform: `rotate(-8deg) scale(${interpolate(s, [0, 1], [2.2, 1])})`,
        opacity: s,
        border: "8px solid #f2e6c9",
        color: "#f2e6c9",
        padding: "6px 26px",
        fontFamily: "Courier New, monospace",
        fontWeight: 900,
        fontSize: tam,
        letterSpacing: 6,
        borderRadius: 10,
        whiteSpace: "nowrap",
        textShadow: "0 4px 18px rgba(0,0,0,0.6)",
        boxShadow: "0 6px 24px rgba(0,0,0,0.4)",
      }}
    >
      {text}
    </div>
  );
};

// ---------- legendas animadas ----------
const MAX_LEGENDA = W - 80; // 40 px de folga de cada lado
const CONTORNO = 14;

// tamanho final do bloco: o `tam` do Python, encolhido só se a linha não couber
const tamDoBloco = (b: Bloco): number => {
  const gap = b.tam * 0.54;
  let w = CONTORNO + gap * Math.max(0, b.palavras.length - 1);
  for (const p of b.palavras) w += medir(p.w, 900, p.destaque || p.censura ? b.tam * 1.12 : b.tam, 1);
  return w > MAX_LEGENDA ? (b.tam * MAX_LEGENDA) / w : b.tam;
};

const Legendas: React.FC = () => {
  const D = useD();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const b = D.legenda.blocos.find((x) => frame >= x.f0 && frame < x.f1);
  const tam = React.useMemo(() => (b ? tamDoBloco(b) : 0), [b]);
  if (!b) return null;
  const local = frame - b.f0;
  const pop = spring({ frame: local, fps, config: { damping: 12, stiffness: 220, mass: 0.6 } });
  return (
    <div
      style={{
        position: "absolute",
        top: D.legenda.top,
        left: 0,
        right: 0,
        display: "flex",
        flexWrap: "nowrap",
        whiteSpace: "nowrap",
        justifyContent: "center",
        alignItems: "baseline",
        columnGap: tam * 0.54,
        transform: `scale(${interpolate(pop, [0, 1], [0.82, 1])}) translateY(${interpolate(pop, [0, 1], [18, 0])}px)`,
        opacity: Math.min(1, pop * 1.5),
      }}
    >
      {b.palavras.map((p, i) => {
        const ativa = frame >= p.f0 - 1 && frame < p.f1 + 2;
        const jaFalou = frame >= p.f0 - 1;
        const cor = p.censura ? VERMELHO : ativa || p.destaque ? D.cor : "white";
        const fs = p.destaque || p.censura ? tam * 1.12 : tam;
        const bump = ativa ? spring({ frame: frame - p.f0, fps, config: { damping: 10, stiffness: 300, mass: 0.5 } }) : 0;
        return (
          <span
            key={i}
            style={{
              fontFamily: FONTE,
              fontWeight: 900,
              fontSize: fs,
              lineHeight: 1.08,
              color: cor,
              opacity: jaFalou ? 1 : 0.92,
              WebkitTextStroke: `${CONTORNO}px black`,
              paintOrder: "stroke fill",
              textShadow: "0 8px 0 rgba(0,0,0,0.55), 0 0 30px rgba(0,0,0,0.35)",
              transform: `scale(${1 + 0.05 * bump}) rotate(${ativa && (p.destaque || p.censura) ? -2 : 0}deg)`,
              display: "inline-block",
              letterSpacing: 1,
            }}
          >
            {p.w}
          </span>
        );
      })}
    </div>
  );
};

// ---------- gancho, crédito e etiqueta ----------
const Gancho: React.FC<{ texto: string; emoji: string | null; dur: number }> = ({ texto, emoji, dur }) => {
  const D = useD();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 11, stiffness: 170 } });
  const sai = interpolate(frame, [dur - 8, dur], [1, 0], CL);
  const balanco = Math.sin(frame / 9) * 1.2;
  const tam = caber(texto + (emoji ? " " + emoji : ""), 900, 62, W - 80 - 68);
  return (
    <div style={{ position: "absolute", top: 210, width: "100%", display: "flex", flexDirection: "column", alignItems: "center", opacity: sai }}>
      <div
        style={{
          transform: `scale(${interpolate(s, [0, 1], [0.4, 1])}) rotate(${-3 + balanco}deg)`,
          background: "white",
          color: "black",
          fontFamily: FONTE,
          fontWeight: 900,
          fontSize: tam,
          padding: "16px 34px 18px",
          borderRadius: 26,
          boxShadow: "0 14px 0 " + D.cor + ", 0 20px 50px rgba(0,0,0,0.45)",
          whiteSpace: "nowrap",
        }}
      >
        {texto}
        {emoji ? <span style={{ fontSize: tam + 2 }}> {emoji}</span> : null}
      </div>
    </div>
  );
};

const Credito: React.FC<{ texto: string; dur: number }> = ({ texto, dur }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - 10, fps, config: { damping: 20 } });
  const sai = interpolate(frame, [dur - 12, dur], [1, 0], CL);
  const tam = caber(texto, 800, 36, W - 80 - 44, 1);
  return (
    <div
      style={{
        position: "absolute",
        top: 370,
        width: "100%",
        textAlign: "center",
        opacity: s * sai,
        transform: `translateY(${interpolate(s, [0, 1], [20, 0])}px)`,
      }}
    >
      <span
        style={{
          fontFamily: FONTE,
          fontWeight: 800,
          fontSize: tam,
          color: "white",
          background: "rgba(0,0,0,0.55)",
          padding: "8px 22px",
          borderRadius: 40,
          letterSpacing: 1,
          whiteSpace: "nowrap",
        }}
      >
        {texto}
      </span>
    </div>
  );
};

const EtiquetaC: React.FC<{ e: Etiqueta; dur: number }> = ({ e, dur }) => {
  const D = useD();
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 10, stiffness: 180 } });
  const sai = interpolate(frame, [dur - 6, dur], [1, 0], CL);
  const tam = caber((e.emoji ? e.emoji + "  " : "") + e.texto, 900, 56, W - 80 - 72);
  return (
    <div style={{ position: "absolute", top: e.top, width: "100%", display: "flex", justifyContent: "center", opacity: sai }}>
      <div
        style={{
          transform: `scale(${s}) rotate(${interpolate(s, [0, 1], [-12, 3])}deg)`,
          background: D.cor,
          color: "black",
          fontFamily: FONTE,
          fontWeight: 900,
          fontSize: tam,
          padding: "14px 30px",
          borderRadius: 18,
          border: "6px solid black",
          boxShadow: "0 10px 30px rgba(0,0,0,0.45)",
          whiteSpace: "nowrap",
        }}
      >
        {e.emoji ? <span style={{ marginRight: 14 }}>{e.emoji}</span> : null}
        {e.texto}
      </div>
    </div>
  );
};

const Marca: React.FC = () => {
  const D = useD();
  if (!D.marca) return null;
  // marca d'água discreta; fica por baixo das imagens, que a cobrem
  return (
    <div
      style={{
        position: "absolute",
        top: D.marca.top,
        width: "100%",
        textAlign: "center",
        fontFamily: "Arial, Helvetica, sans-serif",
        fontWeight: 700,
        fontSize: 104,
        letterSpacing: 4,
        color: "white",
        whiteSpace: "nowrap",
        opacity: D.marca.opacidade,
      }}
    >
      {D.marca.texto}
    </div>
  );
};

const Progresso: React.FC = () => {
  const D = useD();
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return <div style={{ position: "absolute", bottom: 0, left: 0, height: 10, width: `${(frame / durationInFrames) * 100}%`, background: D.cor }} />;
};

// ---------- áudio ----------
const Sons: React.FC = () => {
  const D = useD();
  const { durationInFrames } = useVideoConfig();
  return (
    <>
      {D.sons.map((s, i) =>
        s.f < durationInFrames ? (
          <Sequence key={"s" + i} from={Math.max(0, s.f)} durationInFrames={Math.max(1, Math.min(s.dur ?? 90, durationInFrames - Math.max(0, s.f)))}>
            <Audio src={staticFile(s.src)} volume={s.vol} />
          </Sequence>
        ) : null,
      )}
      {D.trilha && <Trilha src={D.trilha.src} vol={D.trilha.vol} dur={durationInFrames} />}
    </>
  );
};

const Trilha: React.FC<{ src: string; vol: number; dur: number }> = ({ src, vol, dur }) => {
  // entra em 15 quadros e sai nos últimos 30
  const fi = Math.min(15, Math.floor(dur / 3));
  const fo = Math.min(30, Math.floor(dur / 3));
  const volume = (fr: number) => (fi < 1 ? vol : vol * interpolate(fr, [0, fi, dur - fo, dur], [0, 1, 1, 0], CL));
  return <Audio src={staticFile(src)} volume={volume} />;
};

// ---------- composição ----------
export const Corte: React.FC<Dados> = (dados) => (
  <Ctx.Provider value={dados}>
    <CorteInner />
  </Ctx.Provider>
);

const CorteInner: React.FC = () => {
  const D = useD();
  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Fundo />
      <Marca />
      {D.imagens.map((b, i) =>
        b.f1 > b.f0 ? (
          <Sequence key={"b" + i} from={b.f0} durationInFrames={b.f1 - b.f0}>
            <ImagemB b={b} dur={b.f1 - b.f0} />
          </Sequence>
        ) : null,
      )}
      <Legendas />
      {D.gancho && D.gancho.f1 > D.gancho.f0 && (
        <Sequence from={D.gancho.f0} durationInFrames={D.gancho.f1 - D.gancho.f0}>
          <Gancho texto={D.gancho.texto} emoji={D.gancho.emoji} dur={D.gancho.f1 - D.gancho.f0} />
        </Sequence>
      )}
      {D.credito && D.credito.f1 > 0 && (
        <Sequence from={0} durationInFrames={D.credito.f1}>
          <Credito texto={D.credito.texto} dur={D.credito.f1} />
        </Sequence>
      )}
      {D.etiquetas.map((e, i) =>
        e.f1 > e.f0 ? (
          <Sequence key={"e" + i} from={e.f0} durationInFrames={e.f1 - e.f0}>
            <EtiquetaC e={e} dur={e.f1 - e.f0} />
          </Sequence>
        ) : null,
      )}
      <Progresso />
      <Sons />
    </AbsoluteFill>
  );
};
