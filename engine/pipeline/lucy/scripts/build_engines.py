#!/usr/bin/env python3
"""Build Lucy's pinned Rust editor forks and install their WebAssembly assets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PATCHES = ROOT / "third_party/patches"
ASSETS = ROOT / "app/src/main/assets/engines"
LOCK = json.loads((ROOT / "engine-lock.json").read_text())


def tool(program, version):
    candidate = os.environ.get("FOLIO_" + program.upper().replace("-", "_")) or shutil.which(program)
    if candidate and version in subprocess.check_output([candidate, "--version"], text=True):
        return candidate
    cache = ROOT / ".cache/tools"
    cache.mkdir(parents=True, exist_ok=True)
    if program == "wasm-bindgen":
        name = f"wasm-bindgen-{version}-x86_64-unknown-linux-musl.tar.gz"
        base = f"https://github.com/wasm-bindgen/wasm-bindgen/releases/download/{version}/"
        suffix = ".sha256sum"
    else:
        name = f"binaryen-version_{version}-x86_64-linux.tar.gz"
        base = f"https://github.com/WebAssembly/binaryen/releases/download/version_{version}/"
        suffix = ".sha256"
    archive = cache / name
    if not archive.exists():
        with urllib.request.urlopen(base + name, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
    with urllib.request.urlopen(base + name + suffix, timeout=30) as response:
        expected = response.read().decode().split()[0]
    if digest(archive) != expected:
        raise ValueError(f"Build-tool checksum mismatch: {name}")
    with tarfile.open(archive) as bundle:
        bundle.extractall(cache, filter="data")
    return str(next(path for path in cache.rglob(program) if path.is_file()))


def prepare_ui_fonts():
    """One pinned OFL font family for every editor menu, without adding font files to forks."""
    spec = LOCK["ui_fonts"]
    folder = ROOT / ".cache/ui-fonts"
    folder.mkdir(parents=True, exist_ok=True)
    for name, expected in spec["files"].items():
        path = folder / name
        if not path.exists():
            url = f'https://raw.githubusercontent.com/{spec["repository"]}/{spec["source_commit"]}/assets/fonts/{name}'
            with urllib.request.urlopen(url, timeout=60) as response, path.open("wb") as output:
                shutil.copyfileobj(response, output)
        if digest(path) != expected:
            raise ValueError(f"Interface-font checksum mismatch: {name}")
    host_fonts = ROOT / "app/src/main/assets/fonts"
    host_fonts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(folder / "Inter-Regular.ttf", host_fonts / "Inter-Regular.ttf")
    return folder



def prepare_translations():
    """Prepare the pinned upstream catalogs or the separate Spanish profile."""
    spec = LOCK["translations"]
    if LOCK.get("language_mode") == "all":
        full = ROOT / ".cache/full-i18n" / spec["source_commit"]
        if not full.exists():
            full.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".catalogs-", dir=full.parent) as temp:
                checkout = Path(temp) / "checkout"
                subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
                subprocess.run(["git", "-C", str(checkout), "remote", "add", "origin", "https://github.com/" + spec["repository"] + ".git"], check=True)
                subprocess.run(["git", "-C", str(checkout), "fetch", "--depth=1", "origin", spec["source_commit"]], check=True)
                subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"], check=True)
                os.replace(checkout, full)
        actual = subprocess.check_output(["git", "-C", str(full), "rev-parse", "HEAD"], text=True).strip()
        if actual != spec["source_commit"]:raise ValueError("La revisión de los idiomas no coincide")
        if not (full / "locales").is_dir():raise ValueError("La descarga de idiomas está incompleta; conservá o quitá esa caché antes de reintentar")
        return full
    folder = ROOT / ".cache/spanish-i18n"
    for name, expected in spec["files"].items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or digest(path) != expected:
            url = f'https://raw.githubusercontent.com/{spec["repository"]}/{spec["source_commit"]}/{name}'
            with urllib.request.urlopen(url, timeout=60) as response, path.open("wb") as output:
                shutil.copyfileobj(response, output)
        if digest(path) != expected:
            raise ValueError(f"Spanish-catalog checksum mismatch: {name}")
    supplement = ROOT / spec["supplement"]
    if digest(supplement) != spec["supplement_sha256"]:
        raise ValueError("Spanish-catalog supplement differs from its pin")
    # The source bytes remain checksum-verifiable; the app reads a separate merged build input.
    merged = ROOT / ".cache/spanish-i18n-build"
    target = merged / "locales/es"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(folder / "locales/es/common.tsv", target / "common.tsv")
    (target / "wordcraft.tsv").write_bytes((folder / "locales/es/wordcraft.tsv").read_bytes() + b"\n" + supplement.read_bytes())
    return merged


def compile_editor(engine, source, env):
    import tomllib
    lock = tomllib.loads((source / "Cargo.lock").read_text())
    bindgen_version = next(p["version"] for p in lock["package"] if p["name"] == "wasm-bindgen")
    bindgen = tool("wasm-bindgen", bindgen_version)
    name = engine["id"] + "-web"
    subprocess.run(["cargo", "build", "--locked", "--release", "--target", "wasm32-unknown-unknown", "--manifest-path", f"apps/{name}/Cargo.toml", "--bin", name], cwd=source, env=env, check=True)
    raw = Path(env["CARGO_TARGET_DIR"]) / "wasm32-unknown-unknown/release" / (name + ".wasm")
    dist = source / "dist/folio-android"
    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    subprocess.run([bindgen, "--target", "web", "--no-typescript", "--weak-refs", "--out-dir", str(dist), "--out-name", name, str(raw)], env=env, check=True)
    wasm = dist / (name + "_bg.wasm")
    if env.get("FOLIO_OPTIMIZE_WASM") == "1":
        optimizer = tool("wasm-opt", "128")
        optimized = dist / (name + "_optimized.wasm")
        subprocess.run([optimizer, "-Oz", "--all-features", str(wasm), "-o", str(optimized)], env={**env, "BINARYEN_CORES": "2"}, check=True)
        optimized.replace(wasm)
    html = (source / f"apps/{name}/index.html").read_text()
    html = re.sub(r'<link\b[^>]*rel="icon"[^>]*>', "", html)
    bootstrap = f'''<script type="module">\nimport init, * as bindings from './{name}.js';\nconst wasm = await init({{module_or_path:'./{name}_bg.wasm'}});\nwindow.wasmBindings = bindings;\ndispatchEvent(new CustomEvent("TrunkApplicationStarted", {{detail:{{wasm}}}}));\n</script>'''
    html, count = re.subn(r'<link\b[^>]*rel="rust"[^>]*>', lambda _: bootstrap, html)
    if count != 1:
        raise ValueError("Expected exactly one Rust WebAssembly entry point")
    (dist / "index.html").write_text(html)


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def prune_source(engine, source):
    """Remove retired UI catalogs without distributing their deleted contents in patches."""
    base = source.resolve()
    for name in engine.get("source_prune", []):
        relative = Path(name)
        target = source / relative
        if relative.is_absolute() or ".." in relative.parts or not target.resolve().is_relative_to(base):
            raise ValueError("Invalid source-pruning path")
        target.unlink(missing_ok=True)


def source_diff(engine, source):
    excluded = [":(exclude)" + name for name in engine.get("source_prune", [])]
    return subprocess.check_output(["git", "diff", "--binary", "HEAD", "--", ".", *excluded], cwd=source)


def verify():
    if digest(ROOT / "app/src/main/assets/fonts/Inter-Regular.ttf") != LOCK["ui_fonts"]["files"]["Inter-Regular.ttf"]:
        raise ValueError("Host interface font differs from its pin")
    if digest(ROOT / LOCK["translations"]["supplement"]) != LOCK["translations"]["supplement_sha256"]:
        raise ValueError("Spanish translation supplement differs from its pin")
    for engine in LOCK["engines"]:
        folder = ASSETS / engine["id"]
        manifest = json.loads((folder / "folio-engine.json").read_text())
        if manifest.get("source_commit") != engine["source_commit"] or manifest.get("patch_sha256") != digest(PATCHES / (engine["id"] + ".patch")) or manifest.get("fonts_commit") != LOCK["fonts"]["source_commit"] or manifest.get("ui_fonts") != LOCK["ui_fonts"]:
            raise ValueError(f'{engine["id"]}: compiled engine does not match the current integration patch')
        if manifest.get("ui_languages") != LOCK["ui_languages"] or manifest.get("source_prune") != engine.get("source_prune", []):
            raise ValueError(f'{engine["id"]}: compiled UI language or pruning policy differs from the source lock')
        if manifest.get("ui_translations") != LOCK["translations"]:
            raise ValueError(f'{engine["id"]}: Spanish translation inputs differ from their pins')
        for name, expected in manifest["files"].items():
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or not (folder / relative).resolve().is_relative_to(folder.resolve()) or digest(folder / relative) != expected:
                raise ValueError(f'{engine["id"]}: asset verification failed: {name}')
        if not any(name.endswith(".wasm") for name in manifest["files"]):
            raise ValueError("Missing WebAssembly binary")
    print("Verified all four custom Lucy editor builds.")


def install(engine, source):
    dist = source / "dist/folio-android"
    if not (dist / "index.html").exists():
        raise FileNotFoundError(f"Build did not produce {dist}/index.html")
    folder = ASSETS / engine["id"]
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for path in dist.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(dist)
        if relative.as_posix() != "index.html" and path.suffix not in {".wasm", ".js"}:
            continue
        data = path.read_bytes()
        if path.name == "index.html":
            html = re.sub(r'<link\s+rel="icon"[^>]*>', "", data.decode())
            html = html.replace('<script type="module">', '<script src="../../engine-adapter.js"></script>\n<script type="module">', 1)
            if "../../engine-adapter.js" not in html:
                raise ValueError("Missing Android adapter injection point")
            data = html.encode()
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for name in ["NOTICE", "LICENSE-MIT", "LICENSE-APACHE"]:
        if (source / name).exists():
            shutil.copyfile(source / name, folder / name)
    files = {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob("*")) if p.is_file()}
    manifest = {"folio_version": "0.10.0", "ui_languages": LOCK["ui_languages"], "ui_translations": LOCK["translations"], "source_prune": engine.get("source_prune", []), "ui_fonts": LOCK["ui_fonts"], "source_commit": engine["source_commit"], "fonts_commit": LOCK["fonts"]["source_commit"], "patch_sha256": digest(PATCHES / (engine["id"] + ".patch")), "files": files}
    (folder / "folio-engine.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f'Installed custom {engine["id"]}.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--optimize-wasm", action="store_true", help="Also run Binaryen for a smaller bundle; this takes considerably longer")
    parser.add_argument("--source-root", type=Path, default=ROOT / ".cache/sources")
    parser.add_argument("--engine", choices=[e["id"] for e in LOCK["engines"]])
    args = parser.parse_args()
    if args.verify:
        verify()
        return
    env = dict(os.environ)
    env.setdefault("CARGO_BUILD_JOBS", "2")
    env.setdefault("CARGO_TARGET_DIR", str(ROOT / ".cache/cargo-target"))
    if args.optimize_wasm:
        env["FOLIO_OPTIMIZE_WASM"] = "1"
    if not args.install_only:
        env["FOLIO_UI_FONT_DIR"] = str(prepare_ui_fonts())
        env["CRAFT_I18N_DIR"] = str(prepare_translations())
        env["CRAFT_I18N_REQUIRED"] = "1"
    fonts = args.source_root.resolve() / "craft-fonts"
    if not args.install_only:
        font_pin = LOCK["fonts"]["source_commit"]
        if not fonts.exists():
            fonts.mkdir(parents=True)
            subprocess.run(["git", "init", "--quiet"], cwd=fonts, check=True)
            subprocess.run(["git", "remote", "add", "origin", "https://github.com/storytold/craft-fonts.git"], cwd=fonts, check=True)
            subprocess.run(["git", "fetch", "--depth=1", "origin", font_pin], cwd=fonts, check=True)
            subprocess.run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=fonts, check=True)
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=fonts, text=True).strip() != font_pin:
            raise ValueError("Supplementary font checkout does not match its pin")
        for line in (fonts / "fonts/manifest.txt").read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            fields = [field.strip() for field in line.split(" | ")]
            if len(fields) < 8 or digest(fonts / fields[2]) != fields[6]:
                raise ValueError("Supplementary font checksum mismatch")
        env["CRAFT_FONTS_DIR"] = str(fonts)
        env["CRAFT_FONTS_REQUIRED"] = "1"
    for engine in LOCK["engines"]:
        if args.engine and engine["id"] != args.engine:
            continue
        source = args.source_root.resolve() / engine["id"]
        if not args.install_only:
            if not source.exists():
                source.mkdir(parents=True)
                subprocess.run(["git", "init", "--quiet"], cwd=source, check=True)
                subprocess.run(["git", "remote", "add", "origin", f'https://github.com/{engine["repository"]}.git'], cwd=source, check=True)
                subprocess.run(["git", "fetch", "--depth=1", "origin", engine["source_commit"]], cwd=source, check=True)
                subprocess.run(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=source, check=True)
                subprocess.run(["git", "apply", "--index", str(PATCHES / (engine["id"] + ".patch"))], cwd=source, check=True)
            head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
            if head != engine["source_commit"]:
                raise ValueError("Editor checkout is not pinned to the required commit")
            prune_source(engine, source)
            actual_patch = source_diff(engine, source)
            if actual_patch != (PATCHES / (engine["id"] + ".patch")).read_bytes():
                raise ValueError("Editor checkout has changes outside the verified integration patch")
            compile_editor(engine, source, env)
        install(engine, source)


if __name__ == "__main__":
    main()
