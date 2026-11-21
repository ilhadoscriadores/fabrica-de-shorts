#!/usr/bin/env bash
# Gera a mídia do exemplo em public/exemplo/ (fica fora do git).
# Uso: bash gerar-exemplo.sh
set -euo pipefail
cd "$(dirname "$0")"
D=public/exemplo
mkdir -p "$D"
FF="ffmpeg -hide_banner -loglevel error -y"

# vídeo base: 6 s, 1920x1080, 30 fps, com um tom de 440 Hz
$FF -f lavfi -i "testsrc2=s=1920x1080:r=30:d=6" \
    -f lavfi -i "sine=frequency=440:sample_rate=48000:duration=6" \
    -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest "$D/base.mp4"

# imagem 1024x1536 (gradiente colorido)
$FF -f lavfi -i "gradients=s=1024x1536:c0=0x1d3557:c1=0xe63946:c2=0xf1c40f:n=3:speed=0.02:seed=7" \
    -frames:v 1 "$D/imagem.png"

# som curto (efeito)
$FF -f lavfi -i "sine=frequency=880:sample_rate=48000:duration=0.35" \
    -af "afade=t=out:st=0.2:d=0.15" -c:a pcm_s16le "$D/som.wav"

# trilha de 6 s (já no tamanho do corte)
$FF -f lavfi -i "sine=frequency=220:sample_rate=48000:duration=6" \
    -f lavfi -i "sine=frequency=330:sample_rate=48000:duration=6" \
    -filter_complex "amix=inputs=2,volume=0.5" -c:a pcm_s16le "$D/trilha.wav"

echo "exemplo pronto em $D"
