FROM ubuntu:24.04
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 unzip xz-utils build-essential pkg-config \
    openjdk-17-jdk-headless libssl-dev libxkbcommon-dev libwayland-dev \
    libudev-dev libasound2-dev libx11-dev libxcursor-dev libxrandr-dev libxi-dev \
    libgl1-mesa-dev libegl1-mesa-dev mesa-vulkan-drivers fonts-noto-cjk \
    && apt-get clean
ENV CADCRAFT_TOOLCHAIN_ROOT=/opt/cadcraft-toolchain
COPY tools/install-toolchain.sh /opt/installer/tools/install-toolchain.sh
RUN bash /opt/installer/tools/install-toolchain.sh
ENV RUSTUP_HOME=/opt/cadcraft-toolchain/rustup \
    CARGO_HOME=/opt/cadcraft-toolchain/cargo \
    RUSTUP_TOOLCHAIN=1.99.1 \
    ANDROID_HOME=/opt/cadcraft-toolchain/android \
    ANDROID_NDK_HOME=/opt/cadcraft-toolchain/android/android-ndk-r28c \
    CARGO_BUILD_JOBS=2 \
    XDG_RUNTIME_DIR=/tmp/cadcraft-runtime
ENV PATH=/opt/cadcraft-toolchain/cargo/bin:$PATH
RUN mkdir -p /tmp/cadcraft-runtime && chmod 700 /tmp/cadcraft-runtime
WORKDIR /project
ENTRYPOINT ["python3", "/project/tablet.py"]
