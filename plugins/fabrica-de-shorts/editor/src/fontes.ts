import { cancelRender, continueRender, delayRender, staticFile } from "remotion";

// Montserrat local (OFL): 800 e 900. Segura o render até as duas carregarem.
export const FONTE = "Montserrat";

const ARQUIVOS: [string, string][] = [
  ["fontes/Montserrat-ExtraBold.ttf", "800"],
  ["fontes/Montserrat-Black.ttf", "900"],
];

if (typeof document !== "undefined") {
  const espera = delayRender("Carregando a Montserrat");
  Promise.all(
    ARQUIVOS.map(([arq, peso]) =>
      new FontFace(FONTE, `url('${staticFile(arq)}') format('truetype')`, { weight: peso }).load(),
    ),
  )
    .then((faces) => {
      faces.forEach((f) => document.fonts.add(f));
      continueRender(espera);
    })
    .catch((err) => cancelRender(err));
}

// Mede um texto na Montserrat (canvas) para encolher o que não cabe na tela.
let ctx: CanvasRenderingContext2D | null = null;
export const medir = (texto: string, peso: number, tam: number, espaco = 0): number => {
  if (typeof document === "undefined") return 0;
  if (!ctx) ctx = document.createElement("canvas").getContext("2d");
  if (!ctx) return 0;
  ctx.font = `${peso} ${tam}px ${FONTE}`;
  return ctx.measureText(texto).width + espaco * [...texto].length;
};

// Maior tamanho (até `tam`) em que o texto cabe em `largura` px.
export const caber = (texto: string, peso: number, tam: number, largura: number, espaco = 0): number => {
  const w = medir(texto, peso, tam, espaco);
  return w > largura ? Math.floor((tam * largura) / w) : tam;
};
