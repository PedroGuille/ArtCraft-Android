# CadCraft Linux Builder 1.1.1

The adapter embedded in Lucy Builder 2.0.3 additionally includes reviewed merges
for CADCraft main 0.16.0 (`096b3f9be427830db5568a3a8ed2e8ba3e41ee66`). See
[the compatibility notes](compat/main-096b3f9b/README.md) and the enclosing
[Lucy Builder validation report](../VALIDACION-2.0.3.md). The standalone launcher
instructions and historical validations below refer to the original Linux kit.

Download official CadCraft source and build its Android Tablet edition with one
command on **Linux x86_64**. The Android adapter stays separate from the desktop
source. No Termux, Android Constructor app, container or GitHub account is needed.

Spanish instructions: [LEEME.md](LEEME.md).

## Run on Fedora

Install system prerequisites once:

```bash
sudo dnf install -y git curl unzip xz python3 java-21-openjdk-devel gcc-c++ make pkgconf-pkg-config
```

Extract this package and run:

```bash
unzip CADCraft-Linux-Builder-1.1.1.zip
cd CADCraft-Linux-Builder-1.1.1
bash build.sh
```

The command downloads the latest stable official source, applies the tablet
adapter, installs its private Rust and Android tools, then compiles and signs an
**ARM64 APK**. The final APK path is printed at the end. Results are in `dist/`,
including the build log, source hashes and the matching native debug symbols.

**Keep this folder between builds.** Downloads and Rust build outputs are reused.
The first build needs an internet connection and several GB of downloads and
disk space; reserve at least 15 GiB free, preferably 25 GiB. Build time depends
on the CPU and network. The script selects up to eight parallel jobs based on
available memory; use `--jobs 2` to reduce memory usage.

Python 3.11+ and a JDK 17+ are required. Java sources target release 17 and
are converted by D8 for Android API 26. The compiler target is checked before
the Rust build starts. On Ubuntu 24.04/Debian with Java 21:

```bash
sudo apt install -y git curl unzip xz-utils python3 openjdk-21-jdk-headless build-essential pkg-config
```

## Other commands

```bash
# Use a specific release instead of the latest.
bash build.sh --version 0.15.1

# Download and combine sources without installing compilers or building an APK.
bash build.sh --prepare-only

# Reduce parallelism.
bash build.sh --jobs 2

# Sign with an existing compatible preview key.
bash build.sh --keystore /absolute/path/preview.keystore
```

A compatible key uses alias `androiddebugkey` and password `android`, matching
previous Tablet preview builds. No private key is included in this package.
When omitted, a key is created at `private/preview.keystore` and reused. Back it
up privately: Android requires the same signing key to update an installed app.
A newly generated key cannot update an APK signed by a different key.

If interrupted, rerun the same command. Completed downloads are checked before
reuse; partial Android SDK/NDK installations are replaced on the next run. The
script does not install system packages, alter your shell configuration or use
an existing Rust installation. It checks prerequisites and shows installation
commands if something is missing. It never publishes to GitHub.

## Updating CadCraft

The tested integration is official **v0.15.1**, revision
`660e15c9f494ce647e87de10adbb01a8786e0901`. Run `bash build.sh` later to select
the latest stable release automatically. Use `--version 0.15.1` for a known input.

The adapter performs a three-way merge using the original desktop base, the
Android changes, and the downloaded desktop source. Independent upstream
changes are preserved. Conflicts stop the build and are recorded in
`work/<revision>-<adapter>/.tablet/report.json`. Unknown future API changes can
still require adapter maintenance even when text merges cleanly. This is an
automatic build workflow, not a guarantee that every future release will be
compatible. The source ZIP is never modified. Edited generated workspaces are
not silently overwritten or reused by the automatic command.

Tools are pinned to Rust 1.99.1, Android API 36, build-tools 36.0.0 and NDK r28c.
Both Rust host and Android libraries come from the matching official Rust
release. NDK Clang links the native library directly; cargo-ndk is not needed.
Downloads have integrity checks. The native library is checked for the selected
ABI, 16 KiB page alignment and dependencies on Android system libraries only.

## Layout and customization

| Path | Purpose |
| --- | --- |
| `build.sh`, `linux.py` | Automatic Linux workflow and source download |
| `tablet.py` | ZIP validation, merge and packaging orchestration |
| `android/` | Android modules, UI, Java activity and packaging |
| `integration/`, `compat/` | Shared-file changes and reviewed compatibility merges |
| `adapter.json` | Source base, tool versions and integrity hashes |
| `cache/` | Downloaded source, SDK/NDK/Rust and compilation cache |
| `work/` | Generated desktop + tablet source |
| `dist/` | APKs, symbols, build logs and provenance |
| `private/` | Persistent signing key; never publish this directory |

To use a source ZIP you already have, or compile intentionally edited generated
source, use the advanced `tablet.py` commands (`python3 tablet.py --help`). Load
the private toolchain environment first, as described in LEEME.md.

After changing owned Android files, run `python3 tools/seal.py`, then prepare a
fresh source workspace. Do not edit `integration/base/`: it is the merge base.

Run adapter and Linux workflow regressions with:

```bash
python3 -m unittest discover -s tests -v
```

Previous Docker launchers are retained for advanced use; they are not part of
the native Linux command. See VALIDACION.md for the checks actually performed.

## License

MIT OR Apache-2.0, as CadCraft. Original notices, licenses and attribution are
preserved. Official desktop sources and dependencies retain their own notices.
