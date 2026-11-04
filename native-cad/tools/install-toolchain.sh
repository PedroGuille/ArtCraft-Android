#!/usr/bin/env bash
# Pinned Linux x86_64 tools, installed outside the source and adapter payload.
set -euo pipefail
[[ "$(uname -sm)" == "Linux x86_64" ]] || { echo 'Requires Linux x86_64 (or Docker --platform linux/amd64).' >&2; exit 1; }
kit="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
toolchain="${CADCRAFT_TOOLCHAIN_ROOT:-$kit/cache/toolchain}"
mkdir -p "$toolchain/downloads" "$toolchain/android/platforms" "$toolchain/android/build-tools"
toolchain="$(cd "$toolchain" && pwd)"
export RUSTUP_HOME="$toolchain/rustup"
export CARGO_HOME="$toolchain/cargo"
export RUSTUP_TOOLCHAIN=1.99.1
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
export PATH="$CARGO_HOME/bin:$PATH"

download() {
    local url="$1" checksum="$2" name="$3" algorithm="${4:-sha1}"
    if [[ -f "$toolchain/downloads/$name" ]] && printf '%s  %s\n' "$checksum" "$toolchain/downloads/$name" | "${algorithm}sum" -c --status; then return; fi
    curl --fail --location --retry 3 --connect-timeout 30 "$url" --output "$toolchain/downloads/$name.part"
    printf '%s  %s\n' "$checksum" "$toolchain/downloads/$name.part" | "${algorithm}sum" -c -
    mv "$toolchain/downloads/$name.part" "$toolchain/downloads/$name"
}
if [[ ! -x "$CARGO_HOME/bin/rustup" ]]; then
    # Immutable bootstrap URL: never mix a cached binary with a newer checksum.
    download https://static.rust-lang.org/rustup/archive/1.28.2/x86_64-unknown-linux-gnu/rustup-init \
        20a06e644b0d9bd2fbdbfd52d42540bdde820ea7df86e92e533c073da0cdd43c rustup-init-1.28.2 sha256
    chmod +x "$toolchain/downloads/rustup-init-1.28.2"
    "$toolchain/downloads/rustup-init-1.28.2" -y --profile minimal --default-toolchain none --no-modify-path
fi
rustup set auto-self-update disable
rustup toolchain install 1.99.1 --profile minimal
rustup target add --toolchain 1.99.1 aarch64-linux-android
stage=''
trap 'if [[ -n "$stage" ]]; then rm -rf -- "$stage"; fi' EXIT
if [[ ! -f "$toolchain/android/platforms/android-36/.complete" ]]; then
    download https://dl.google.com/android/repository/platform-36_r02.zip 2c1a80dd4d9f7d0e6dd336ec603d9b5c55a6f576 platform-36.zip
    stage="$(mktemp -d "$toolchain/platform.XXXXXX")"
    unzip -q "$toolchain/downloads/platform-36.zip" -d "$stage"
    platform="$(find "$stage" -name android.jar -printf '%h\n' -quit)"
    [[ -n "$platform" ]] || { echo 'Android SDK archive has changed.' >&2; exit 1; }
    touch "$platform/.complete"
    rm -rf -- "$toolchain/android/platforms/android-36"
    mv "$platform" "$toolchain/android/platforms/android-36"
    rm -rf -- "$stage"; stage=''
fi
if [[ ! -f "$toolchain/android/build-tools/36.0.0/.complete" ]]; then
    download https://dl.google.com/android/repository/build-tools_r36_linux.zip b0b6376977657e8ad9b969bacf4093601da2c6fb build-tools-36.zip
    stage="$(mktemp -d "$toolchain/build-tools.XXXXXX")"
    unzip -q "$toolchain/downloads/build-tools-36.zip" -d "$stage"
    tools="$(find "$stage" -name aapt2 -printf '%h\n' -quit)"
    [[ -n "$tools" ]] || { echo 'Android build-tools archive has changed.' >&2; exit 1; }
    [[ -x "$tools/zipalign" && -x "$tools/apksigner" && -x "$tools/d8" ]]
    touch "$tools/.complete"
    rm -rf -- "$toolchain/android/build-tools/36.0.0"
    mv "$tools" "$toolchain/android/build-tools/36.0.0"
    rm -rf -- "$stage"; stage=''
fi
if [[ ! -f "$toolchain/android/android-ndk-r28c/.complete" ]]; then
    download https://dl.google.com/android/repository/android-ndk-r28c-linux.zip a7b54a5de87fecd125a17d54f73c446199e72a64 android-ndk-r28c.zip
    stage="$(mktemp -d "$toolchain/ndk.XXXXXX")"
    unzip -q "$toolchain/downloads/android-ndk-r28c.zip" -d "$stage"
    [[ -x "$stage/android-ndk-r28c/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" ]]
    touch "$stage/android-ndk-r28c/.complete"
    rm -rf -- "$toolchain/android/android-ndk-r28c"
    mv "$stage/android-ndk-r28c" "$toolchain/android/android-ndk-r28c"
    rm -rf -- "$stage"; stage=''
fi
echo "Toolchain ready: $toolchain"
