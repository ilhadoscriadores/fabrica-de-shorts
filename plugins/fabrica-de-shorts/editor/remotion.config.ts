import { Config } from "@remotion/cli/config";

// Quadros em JPEG (mais rápido) no Corte.
Config.setVideoImageFormat("jpeg");

// No Windows o Chrome desenha os quadros pela GPU.
if (process.platform === "win32") {
  Config.setChromiumOpenGlRenderer("angle");
}
