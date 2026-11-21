// Dados de um corte. O Python grava isto no dados.json; o editor só desenha.
// Todos os tempos em quadros inteiros a 30 fps.

export type Palavra = { w: string; f0: number; f1: number; destaque: boolean; censura: boolean };

export type Bloco = { f0: number; f1: number; tam: number; palavras: Palavra[] };

export type Imagem = {
  src: string;
  f0: number;
  f1: number;
  entrada: "zoom" | "flash" | "slide-esq" | "slide-dir";
  movimento: "in-left" | "in-right" | "out" | "up";
  tremidas: number[]; // quadros absolutos do corte
  carimbo: string | null;
  sepia: boolean;
  sirene: boolean;
};

export type Etiqueta = { f0: number; f1: number; texto: string; emoji: string | null; top: number };

export type Som = { src: string; f: number; vol: number; dur?: number }; // dur em quadros (padrão 90)

export type Dados = {
  fps: 30;
  duracaoFrames: number;
  base: { src: string; largura: number; altura: number }; // src relativo a public/
  camera: { f: number; cx: number; cy: number }[]; // cx, cy de 0 a 1; dois pontos no mesmo f = corte seco
  zoom: boolean;
  cor: string; // cor de destaque
  legenda: { top: number; blocos: Bloco[] };
  gancho: { texto: string; emoji: string | null; f0: number; f1: number } | null;
  credito: { texto: string; f1: number } | null;
  imagens: Imagem[];
  etiquetas: Etiqueta[];
  marca: { texto: string; top: number; opacidade: number } | null;
  sons: Som[]; // todo efeito, whoosh e bipe de censura, já expandidos
  trilha: { src: string; vol: number } | null; // já em loop no tamanho do corte e com ducking
  selo: null;
};

export type SeloProps = { lado: "esq" | "dir"; cor: string };
