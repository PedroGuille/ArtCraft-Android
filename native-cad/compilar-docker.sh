#!/usr/bin/env bash
# Copy the original source ZIP into this folder, then run this launcher.
set -euo pipefail
kit="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$kit"
source_zip="${1:-}"
if [[ -z "$source_zip" ]]; then
    # Avoid mapfile: macOS still provides Bash 3.2 as its system Bash.
    for candidate in ./*.zip; do
        [[ -f "$candidate" ]] || continue
        [[ -z "$source_zip" ]] || { echo 'Deja solo un ZIP original de CadCraft junto a este lanzador.' >&2; exit 2; }
        source_zip="$candidate"
    done
    [[ -n "$source_zip" ]] || { echo 'Pon un ZIP original de CadCraft en esta carpeta, o indica su nombre.' >&2; exit 2; }
fi
[[ -f "$source_zip" && "$(cd "$(dirname "$source_zip")" && pwd)" == "$kit" ]] || { echo 'Copia el ZIP original a la misma carpeta que este lanzador.' >&2; exit 2; }
source_zip="$(basename "$source_zip")"
command -v docker >/dev/null || { echo 'Instala e inicia Docker Desktop (o Docker Engine en Linux).' >&2; exit 1; }
docker build --platform linux/amd64 -t cadcraft-tablet-builder:1.0 .
# The named Cargo cache survives container runs. The generated sources, APK,
# symbols and signing key stay in the mounted project, not the container.
docker run --rm --platform linux/amd64 \
    --mount "type=bind,src=$kit,dst=/project" \
    --mount type=volume,src=cadcraft-tablet-cargo-registry,dst=/opt/cadcraft-toolchain/cargo/registry \
    --mount type=volume,src=cadcraft-tablet-cargo-git,dst=/opt/cadcraft-toolchain/cargo/git \
    cadcraft-tablet-builder:1.0 build "/project/$source_zip" --output "/project/work/$source_zip" --artifacts /project/dist
