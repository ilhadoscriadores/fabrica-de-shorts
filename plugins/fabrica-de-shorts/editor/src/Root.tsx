import React from "react";
import { Composition } from "remotion";
import { Corte } from "./Corte";
import { Selo, SELO_QUADROS } from "./Selo";
import type { Dados, SeloProps } from "./tipos";
import "./fontes";

// Padrão só para o Studio abrir (rode antes o gerar-exemplo.sh). O Python manda o dados.json com --props.
const PADRAO: Dados = {
  fps: 30,
  duracaoFrames: 180,
  base: { src: "exemplo/base.mp4", largura: 1920, altura: 1080 },
  camera: [{ f: 0, cx: 0.5, cy: 0.5 }],
  zoom: true,
  cor: "#FFD60A",
  legenda: {
    top: 1180,
    blocos: [
      {
        f0: 0,
        f1: 90,
        tam: 92,
        palavras: [
          { w: "ABRA", f0: 0, f1: 30, destaque: false, censura: false },
          { w: "O", f0: 30, f1: 45, destaque: false, censura: false },
          { w: "EXEMPLO", f0: 45, f1: 90, destaque: true, censura: false },
        ],
      },
    ],
  },
  gancho: { texto: "FÁBRICA DE SHORTS", emoji: "🎬", f0: 0, f1: 60 },
  credito: { texto: "Exemplo • Fábrica de Shorts", f1: 75 },
  imagens: [],
  etiquetas: [],
  marca: { texto: "@FABRICA", top: 980, opacidade: 0.08 },
  sons: [],
  trilha: null,
  selo: null,
};

export const Root: React.FC = () => (
  <>
    <Composition
      id="Corte"
      component={Corte}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={PADRAO.duracaoFrames}
      defaultProps={PADRAO}
      calculateMetadata={({ props }) => ({ durationInFrames: Math.max(1, Math.round(props.duracaoFrames)) })}
    />
    <Composition
      id="Selo"
      component={Selo}
      width={1080}
      height={200}
      fps={30}
      durationInFrames={SELO_QUADROS}
      defaultProps={{ lado: "esq", cor: "#e10600" } as SeloProps}
      // fundo transparente pede quadros em PNG (vence o JPEG do remotion.config.ts)
      calculateMetadata={() => ({
        defaultVideoImageFormat: "png",
        defaultCodec: "prores",
        defaultProResProfile: "4444",
        defaultPixelFormat: "yuva444p10le",
      })}
    />
  </>
);
