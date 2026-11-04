#!/usr/bin/env python3
"""Download official desktop source and build the separate tablet adapter on Linux."""
from __future__ import annotations
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import tablet

ROOT = Path(__file__).resolve().parent
VERSION = "1.1.1"
ALLOWED = {"api.github.com", "codeload.github.com", "github.com"}

class BuilderError(Exception):
    pass

class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        validate_url(url)
        return super().redirect_request(request, fp, code, msg, headers, url)

def validate_url(url):
    value = urllib.parse.urlsplit(url)
    if value.scheme != "https" or value.hostname not in ALLOWED or value.username or value.password or value.port not in (None, 443):
        raise BuilderError("El servidor de descarga no está permitido.")

def open_url(url):
    validate_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "CADCraft-Linux-Builder/" + VERSION})
    try:
        return urllib.request.build_opener(Redirect()).open(request, timeout=90)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429):
            raise BuilderError("GitHub limitó temporalmente las descargas. Reintenta más tarde; no se borró la caché.") from exc
        raise

def metadata(path):
    with open_url("https://api.github.com/repos/storytold/cadcraft/" + path) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise BuilderError("La respuesta de GitHub supera el límite previsto.")
    return json.loads(raw)

def stable_tag(value):
    if not isinstance(value, str) or not re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", value):
        raise BuilderError("Usa una versión estable como 0.15.1 o v0.15.1.")
    return value

def download_source(cache, version=None):
    if version is None:
        release = metadata("releases/latest")
        if release.get("draft") or release.get("prerelease"):
            raise BuilderError("GitHub no devolvió una publicación estable.")
        tag = stable_tag(release.get("tag_name", ""))
    else:
        tag = stable_tag(version)
        tag = tag if tag.startswith("v") else "v" + tag
    commit = metadata("commits/" + tag).get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise BuilderError("GitHub no devolvió una revisión válida.")
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / ("cadcraft-" + commit + ".zip")
    manifest = archive.with_suffix(".json")
    reuse = False
    if archive.is_file() and manifest.is_file():
        try:
            saved = json.loads(manifest.read_text())
            reuse = saved.get("commit") == commit and saved.get("sha256") == tablet.file_sha(archive)
        except (OSError, ValueError):
            pass
    if not reuse:
        print(f"Descargando código oficial {tag} ({commit[:12]})…", flush=True)
        part = archive.with_suffix(".part")
        try:
            total = 0
            with open_url("https://codeload.github.com/storytold/cadcraft/zip/" + commit) as response, part.open("wb") as output:
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 64 * 1024 * 1024:
                        raise BuilderError("El ZIP supera el límite de 64 MiB.")
                    output.write(block)
            # Full bounded source validation is performed by tablet.prepare.
            part.replace(archive)
            tablet.write_json(manifest, {"tag": tag, "commit": commit, "sha256": tablet.file_sha(archive)})
        finally:
            part.unlink(missing_ok=True)
    return archive, tag, commit

def default_jobs():
    available = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    memory_jobs = max(1, available // (3 * 1024**3)) if available else 2
    return int(min(8, os.cpu_count() or 1, memory_jobs))

def build_env(root, jobs):
    tools = Path(os.environ.get("CADCRAFT_TOOLCHAIN_ROOT", str(root / "cache/toolchain"))).expanduser().resolve()
    env = os.environ.copy()
    for name in ("RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTC", "CARGO_BUILD_TARGET"):
        env.pop(name, None)
    env.update(RUSTUP_HOME=str(tools / "rustup"), CARGO_HOME=str(tools / "cargo"),
               RUSTUP_TOOLCHAIN="1.99.1", ANDROID_HOME=str(tools / "android"),
               ANDROID_NDK_HOME=str(tools / "android/android-ndk-r28c"),
               CARGO_BUILD_JOBS=str(jobs), CARGO_TARGET_DIR=str(root / "cache/target-linux-rust1.99.1-ndk28c"),
               CARGO_NET_GIT_FETCH_WITH_CLI="true", GIT_TERMINAL_PROMPT="0")
    env["PATH"] = str(tools / "cargo/bin") + os.pathsep + env.get("PATH", "")
    return env

@contextlib.contextmanager
def environment(env):
    original = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(env)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)

def prerequisites():
    if sys.platform != "linux" or os.uname().machine != "x86_64":
        raise BuilderError("Este compilador automático requiere Linux x86_64.")
    missing = [name for name in ("git", "curl", "unzip", "xz", "java", "keytool", "cc", "c++", "make", "pkg-config") if not shutil.which(name)]
    if missing:
        raise BuilderError("Faltan herramientas: " + ", ".join(missing) + "\nFedora: sudo dnf install -y git curl unzip xz python3 java-21-openjdk-devel gcc-c++ make pkgconf-pkg-config\nUbuntu/Debian: sudo apt install -y git curl unzip xz-utils python3 openjdk-21-jdk-headless build-essential pkg-config")
    compiler = subprocess.run(["java", "--module", "jdk.compiler/com.sun.tools.javac.Main", "-version"], capture_output=True)
    if compiler.returncode:
        raise BuilderError("Falta el compilador de Java. En Fedora instala java-21-openjdk-devel.")
    java = subprocess.run(["java", "-version"], capture_output=True, text=True, check=True)
    value = re.search(r'version\s+"(\d+)', java.stderr + java.stdout)
    if not value or int(value.group(1)) < 17:
        raise BuilderError("Se necesita un JDK de Java 17 o posterior; se recomienda Java 21.")
    # Check the actual target before downloading/building Rust dependencies. A
    # compiler's version alone does not guarantee support for a --release value.
    with tempfile.TemporaryDirectory(prefix="cadcraft-java-") as temporary:
        source = Path(temporary) / "TabletProbe.java"
        source.write_text("final class TabletProbe {}\n", encoding="utf-8")
        probe = subprocess.run(["java", "--module", "jdk.compiler/com.sun.tools.javac.Main",
                                "--release", "17", "-d", temporary, str(source)],
                               capture_output=True, text=True)
    if probe.returncode:
        raise BuilderError("El JDK actual no puede compilar para Java 17. Usa un JDK completo 17 o 21.\n" + (probe.stderr or probe.stdout).strip())

def main(argv=None):
    parser = argparse.ArgumentParser(description="Un comando: descargar CadCraft y compilar su edición Tablet en Linux")
    parser.add_argument("--version", help="Versión estable concreta; por defecto la última publicación")
    parser.add_argument("--jobs", type=int, default=default_jobs())
    parser.add_argument("--keystore", type=Path, help="Firma anterior (alias androiddebugkey, contraseña android)")
    parser.add_argument("--prepare-only", action="store_true", help="Descargar e integrar, sin instalar SDK ni compilar")
    args = parser.parse_args(argv)
    if args.jobs < 1 or args.jobs > 64:
        parser.error("--jobs debe estar entre 1 y 64")
    try:
        if args.keystore and not args.keystore.expanduser().is_file():
            raise BuilderError("No se encuentra la firma indicada.")
        if not shutil.which("git"):
            raise BuilderError("Instala Git antes de preparar la fuente.")
        if not args.prepare_only:
            prerequisites()
        (ROOT / "cache").mkdir(exist_ok=True)
        with (ROOT / "cache/build.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BuilderError("Ya hay una compilación ejecutándose desde esta carpeta.") from exc
            print("Buscando la versión oficial de CadCraft…", flush=True)
            archive, tag, commit = download_source(ROOT / "cache/source", args.version)
            adapter, adapter_id = tablet.load_adapter(ROOT)
            workspace = ROOT / "work" / (commit[:16] + "-" + adapter_id[:12])
            if workspace.exists():
                _, report = tablet.load_prepared(workspace, ROOT)
                if report["input_zip_sha256"] != tablet.file_sha(archive):
                    raise BuilderError("La carpeta preparada no coincide con la fuente descargada.")
                current = tablet.tree_hashes(workspace)
                expected = dict(report["source_hashes"])
                if report.get("resolved_lock_sha256"):
                    expected["Cargo.lock"] = report["resolved_lock_sha256"]
                if current != expected:
                    raise BuilderError("La fuente preparada fue editada. Usa tablet.py compile para recompilar tus cambios deliberadamente.")
            else:
                print("Integrando la interfaz y las optimizaciones de tablet…", flush=True)
                report = tablet.prepare(archive, workspace, ROOT)
            if report["upstream_version"] != tag.removeprefix("v"):
                raise BuilderError("La versión del ZIP no coincide con la publicación.")
            if report["conflicts"]:
                tablet.print_report(report, workspace)
                return 2
            tablet.print_report(report, workspace)
            if args.prepare_only:
                print("Fuente lista; no se instalaron compiladores ni se creó una APK.")
                return 0
            env = build_env(ROOT, args.jobs)
            print(f"Preparando herramientas (Rust oficial + Android NDK); compilación con {args.jobs} trabajos…", flush=True)
            subprocess.run(["bash", str(ROOT / "tools/install-toolchain.sh")], env=env, check=True)
            # tablet.compile_prepared reads its environment when invoking Cargo.
            artifacts = ROOT / "dist" / (report["upstream_version"] + "-" + commit[:12])
            with environment(env):
                result = tablet.compile_prepared(workspace, artifacts, "arm64-v8a", args.keystore.expanduser() if args.keystore else None, kit=ROOT)
            print("\nAPK: " + result["apk"] + "\nFirma conservada en: " + str(args.keystore or ROOT / "private/preview.keystore") + "\nSímbolos: " + result["symbols"])
            return 0
    except (BuilderError, tablet.AdapterError, OSError, ValueError, zipfile.BadZipFile, urllib.error.URLError, subprocess.CalledProcessError) as exc:
        print("Error: " + str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCompilación interrumpida. Vuelve a ejecutar build.sh para reutilizar la caché.", file=sys.stderr)
        return 130

if __name__ == "__main__":
    raise SystemExit(main())
