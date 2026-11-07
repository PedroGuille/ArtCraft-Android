#!/usr/bin/env python3
"""Build the separate CadCraft tablet adapter on top of an upstream source ZIP.

Python 3.11+ and Git are enough for preparation. Compilation uses the pinned
Linux toolchain (or the supplied Docker image). No third-party Python modules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile

KIT = Path(__file__).resolve().parent
REPORT = ".tablet/report.json"
MAX_FILES = 30_000
MAX_TOTAL = 512 * 1024 * 1024
MAX_FILE = 64 * 1024 * 1024


class AdapterError(Exception):
    """An actionable input, integration or compilation error."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def relative_name(name: str) -> str:
    # Reject Windows paths even when running on Linux, for portable extraction.
    parts = name.split("/")
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or any(ord(c) < 32 for c in name)
            or any(p in ("", ".", "..") or p.endswith((" ", ".")) for p in parts)):
        raise AdapterError(f"Ruta no permitida en el ZIP: {name!r}")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
    if any(p.split(".")[0].lower() in reserved for p in parts):
        raise AdapterError(f"Nombre reservado en el ZIP: {name!r}")
    if any(p.lower() in (".git", ".tablet") for p in parts):
        raise AdapterError(f"El ZIP debe contener código fuente, sin {name!r}")
    return PurePosixPath(name).as_posix()


def checked_payload(root: Path, name: str, expected: str) -> bytes:
    path = root / relative_name(name)
    if not path.is_file() or path.is_symlink():
        raise AdapterError(f"Falta un archivo del adaptador: {name}")
    data = path.read_bytes()
    if sha(data) != expected:
        raise AdapterError(f"Cambió {name}. Actualiza sus hashes con tools/seal.py antes de usarlo.")
    return data


def load_adapter(kit: Path) -> tuple[dict, str]:
    raw = (kit / "adapter.json").read_bytes()
    adapter = json.loads(raw)
    if adapter.get("format") != 1:
        raise AdapterError("Formato de adaptador no compatible.")
    checked_payload(kit, "integration/desktop.patch", adapter["patch_sha256"])
    checked_payload(kit, "integration/base/Cargo.lock", adapter["lock"]["base_sha256"])
    checked_payload(kit, "integration/tablet-Cargo.lock", adapter["lock"]["tablet_sha256"])
    seen = set()
    for record in adapter["modified"]:
        name = relative_name(record["path"])
        if name.casefold() in seen:
            raise AdapterError(f"Archivo repetido en adapter.json: {name}")
        seen.add(name.casefold())
        checked_payload(kit, "integration/base/" + name, record["base_sha256"])
    for record in adapter["owned"]:
        name = relative_name(record["path"])
        if name.casefold() in seen:
            raise AdapterError(f"Archivo repetido en adapter.json: {name}")
        seen.add(name.casefold())
        checked_payload(kit, record["source"], record["sha256"])
    for record in adapter.get("compatible_merges", []):
        relative_name(record["path"])
        for key in ("desktop_sha256", "android_sha256", "sha256"):
            if not re.fullmatch(r"[a-f0-9]{64}", record[key]):
                raise AdapterError("Hash de compatibilidad inválido.")
        checked_payload(kit, record["source"], record["sha256"])
    for profile in adapter.get("source_profiles", []):
        if not profile.get("match") or not profile.get("files"):
            raise AdapterError("Perfil de fuentes vacío.")
        for name, expected in profile["match"].items():
            relative_name(name)
            if not re.fullmatch(r"[a-f0-9]{64}", expected):
                raise AdapterError("Hash de fuentes inválido.")
        for record in profile["files"]:
            relative_name(record["path"])
            checked_payload(kit, record["source"], record["sha256"])
    # Hashes in the manifest cover source files. Include the builder too, so an
    # output cannot be silently reused after its integration algorithm changes.
    return adapter, sha(raw + (kit / "tablet.py").read_bytes())


def git_env() -> dict:
    env = os.environ.copy()
    # A generated build workspace must not inherit another checkout/index.
    for name in tuple(env):
        if name.startswith("GIT_"):
            env.pop(name)
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    return env


def git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", *args], cwd=cwd, env=git_env(), capture_output=True)
    if check and result.returncode:
        raise AdapterError("Git: " + result.stderr.decode(errors="replace").strip())
    return result


def require_git() -> None:
    if not shutil.which("git"):
        raise AdapterError("Instala Git para preparar el código; no se necesita una cuenta de GitHub.")


def extract_source(archive: Path, output: Path) -> dict:
    """Validate every entry before writing any archive-controlled file."""
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > MAX_FILES:
            raise AdapterError(f"El ZIP supera el límite de {MAX_FILES} entradas.")
        total = 0
        names = set()
        validated = []
        for item in entries:
            name = relative_name(item.filename.rstrip("/"))
            folded = name.casefold()
            if folded in names:
                raise AdapterError(f"Ruta repetida en el ZIP: {name}")
            names.add(folded)
            kind = stat.S_IFMT(item.external_attr >> 16)
            if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise AdapterError(f"El ZIP contiene un enlace o archivo especial: {name}")
            if item.flag_bits & 1:
                raise AdapterError("No se admiten ZIP cifrados.")
            total += item.file_size
            if item.file_size > MAX_FILE or total > MAX_TOTAL:
                raise AdapterError("El ZIP supera el límite de extracción de código fuente (512 MiB / 64 MiB por archivo).")
            validated.append((item, name))
        files = [name for item, name in validated if not item.is_dir()]
        roots = []
        for name in files:
            if name == "Cargo.toml" or name.endswith("/Cargo.toml"):
                prefix = name.removesuffix("Cargo.toml")
                if all((prefix + required).casefold() in names for required in (
                    "crates/engine/Cargo.toml", "crates/ui-egui/Cargo.toml", "Cargo.lock",
                )):
                    roots.append(prefix)
        if len(roots) != 1:
            raise AdapterError("Selecciona el ZIP de código fuente original de CadCraft: no se encontró una única raíz de proyecto.")
        prefix = roots[0]
        for item, name in validated:
            if not name.startswith(prefix) or item.is_dir():
                continue
            relative = relative_name(name[len(prefix):])
            dest = output / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                with z.open(item) as src, dest.open("xb") as dst:
                    copied = 0
                    while block := src.read(1024 * 1024):
                        copied += len(block)
                        if copied > item.file_size or copied > MAX_FILE:
                            raise AdapterError(f"Tamaño inesperado al extraer {name}")
                        dst.write(block)
            except (FileExistsError, IsADirectoryError, NotADirectoryError) as exc:
                raise AdapterError(f"Rutas incompatibles dentro del ZIP: {name}") from exc
            # GitHub ZIPs may not retain executable bits; Rust build scripts are
            # source, shell entry points are made executable deterministically.
            dest.chmod(0o755 if relative.endswith(".sh") else 0o644)
    return tomllib.loads((output / "Cargo.toml").read_text(encoding="utf-8"))


def tablet_files(kit: Path, adapter: dict, temporary: Path) -> dict[str, bytes]:
    for record in adapter["modified"]:
        name = record["path"]
        dest = temporary / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((kit / "integration/base" / name).read_bytes())
    git("init", "--quiet", "--template=", str(temporary))
    patch = str((kit / "integration/desktop.patch").resolve())
    git("apply", "--check", patch, cwd=temporary)
    git("apply", patch, cwd=temporary)
    result = {}
    for record in adapter["modified"]:
        data = (temporary / record["path"]).read_bytes()
        if sha(data) != record["tablet_sha256"]:
            raise AdapterError(f"El parche no reproduce la adaptación esperada: {record['path']}")
        result[record["path"]] = data
    return result


def merge_one(incoming: bytes, base: bytes, android: bytes, temp: Path) -> tuple[bytes, bool]:
    if incoming == base:
        return android, True
    if incoming == android or android == base:
        return incoming, True
    for name, data in (("incoming", incoming), ("base", base), ("android", android)):
        (temp / name).write_bytes(data)
    result = git("merge-file", "-p", "--diff3", "-L", "desktop", "-L", "base", "-L", "android",
                 str(temp / "incoming"), str(temp / "base"), str(temp / "android"), check=False)
    if result.returncode == 0:
        return result.stdout, True
    if not result.stdout:
        return result.stderr or b"No se pudo combinar este archivo.\n", False
    return result.stdout, False


def version_info(manifest: dict) -> tuple[str, int]:
    version = manifest.get("workspace", {}).get("package", {}).get("version", "")
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        raise AdapterError("Se necesita una versión estable X.Y.Z en workspace.package.version.")
    major, minor, patch = map(int, match.groups())
    code = major * 1_000_000 + minor * 1_000 + patch
    if minor >= 1000 or patch >= 1000 or not 0 < code <= 2_100_000_000:
        raise AdapterError("La versión no cabe en un versionCode de Android.")
    return version, code


def tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): file_sha(p) for p in sorted(root.rglob("*"))
            if p.is_file() and not set(p.relative_to(root).parts) & {".git", ".tablet", "dist", "target"}}


def prepare(archive: Path, output: Path, kit: Path = KIT) -> dict:
    require_git()
    archive, output = archive.resolve(), output.resolve()
    if not archive.is_file():
        raise AdapterError(f"No se encuentra el ZIP: {archive}")
    if output.exists():
        raise AdapterError(f"Ya existe {output}. Usa otra carpeta, o 'compile' para recompilar la preparada.")
    adapter, adapter_digest = load_adapter(kit)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"format": 1, "adapter_version": adapter["adapter_version"], "adapter_digest": adapter_digest,
              "input_zip_sha256": file_sha(archive), "input_zip": archive.name,
              "base_upstream": adapter["upstream"], "status": "preparing", "conflicts": [],
              "physical_device_tested": False}
    with tempfile.TemporaryDirectory(prefix=".tablet-prepare-", dir=output.parent) as work:
        work = Path(work)
        source = work / "source"
        source.mkdir()
        upstream_manifest = extract_source(archive, source)
        if (source / "apps/cadcraft-android/Cargo.toml").exists():
            raise AdapterError("El ZIP ya incluye la adaptación Android. Utiliza el código fuente original de escritorio.")
        version, code = version_info(upstream_manifest)
        report.update(upstream_version=version, android_version_code=code)
        original_hashes = tree_hashes(source)
        report["exact_base"] = all(original_hashes.get(r["path"]) == r["base_sha256"] for r in adapter["modified"])
        with tempfile.TemporaryDirectory(prefix="tablet-patch-") as patch_temp:
            android_files = tablet_files(kit, adapter, Path(patch_temp))
        with tempfile.TemporaryDirectory(prefix="tablet-merge-") as merge_temp:
            for record in adapter["modified"]:
                name = record["path"]
                path = source / name
                base = (kit / "integration/base" / name).read_bytes()
                target = android_files[name]
                if not path.is_file():
                    report["conflicts"].append({"path": name, "reason": "El original eliminó o movió este archivo."})
                    continue
                incoming = path.read_bytes()
                merged, ok = merge_one(incoming, base, target, Path(merge_temp))
                if not ok:
                    # Reviewed combinations apply only to the exact incoming and
                    # Android bytes. Never overwrite a future, different change.
                    for known in adapter.get("compatible_merges", []):
                        if known["path"] == name and known["desktop_sha256"] == sha(incoming) and known["android_sha256"] == sha(target):
                            merged = checked_payload(kit, known["source"], known["sha256"])
                            ok = True
                            break
                if ok:
                    path.write_bytes(merged)
                    path.chmod(record["mode"])
                else:
                    reason = "Cambios de escritorio y Android en la misma parte del archivo."
                    report["conflicts"].append({"path": name, "reason": reason})
                    for suffix, data in (("desktop", incoming), ("base", base), ("android", target), ("merge", merged)):
                        dest = source / ".tablet/conflicts" / (name + "." + suffix)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(data)
        for record in adapter["owned"]:
            path = source / record["path"]
            data = (kit / record["source"]).read_bytes()
            if path.exists() and (not path.is_file() or path.read_bytes() != data):
                report["conflicts"].append({"path": record["path"], "reason": "La nueva versión ya contiene otro archivo con este nombre."})
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(record["mode"])
        # New upstream APIs can require different tablet-owned modules too.
        # Use a reviewed combination only when every relevant original input
        # matches; older bases keep their original integration unchanged.
        for profile in adapter.get("source_profiles", []):
            if not all(original_hashes.get(name) == expected for name, expected in profile["match"].items()):
                continue
            replaced = set()
            for record in profile["files"]:
                name = relative_name(record["path"])
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(checked_payload(kit, record["source"], record["sha256"]))
                path.chmod(record.get("mode", 0o644))
                replaced.add(name)
            report["conflicts"] = [row for row in report["conflicts"] if row["path"] not in replaced]
            report["source_profile"] = profile["id"]
            break
        # The lock file is NOT text-merged. For the known upstream snapshot use
        # the reviewed tablet lock. For newer snapshots, Cargo resolves only
        # the additional Android packages against the incoming lock at build time.
        original_lock = (source / "Cargo.lock").read_bytes()
        (source / ".tablet").mkdir(exist_ok=True)
        (source / ".tablet/upstream-Cargo.lock").write_bytes(original_lock)
        if sha(original_lock) == adapter["lock"]["base_sha256"]:
            (source / "Cargo.lock").write_bytes((kit / "integration/tablet-Cargo.lock").read_bytes())
            report["lock_status"] = "reviewed_0.14"
        else:
            report["lock_status"] = "needs_android_resolution"
        if not report["conflicts"]:
            combined = tomllib.loads((source / "Cargo.toml").read_text(encoding="utf-8"))
            if version_info(combined)[0] != version:
                raise AdapterError("La integración alteró la versión de escritorio.")
            manifest = source / "packaging/android/AndroidManifest.xml"
            text = manifest.read_text(encoding="utf-8")
            text, ncode = re.subn(r'android:versionCode="\d+"', f'android:versionCode="{code}"', text, count=1)
            text, nname = re.subn(r'android:versionName="[^"]+"', f'android:versionName="{version}"', text, count=1)
            if (ncode, nname) != (1, 1):
                raise AdapterError("No se encontró la versión en AndroidManifest.xml.")
            manifest.write_text(text, encoding="utf-8")
            report["status"] = "prepared_not_compiled"
            report["source_hashes"] = tree_hashes(source)
            git("init", "--quiet", "--template=", str(source))
            (source / ".git/info").mkdir(parents=True, exist_ok=True)
            (source / ".git/info/exclude").write_text(".tablet/\ndist/\ntarget/\n", encoding="utf-8")
            git("add", "--all", "--", ".", cwd=source)
        else:
            report["status"] = "integration_conflicts"
        write_json(source / REPORT, report)
        source.rename(output)
    return report


def load_prepared(root: Path, kit: Path = KIT) -> tuple[dict, dict]:
    adapter, current_digest = load_adapter(kit)
    try:
        report = json.loads((root / REPORT).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdapterError("La carpeta no fue preparada por este adaptador.") from exc
    if report.get("status") == "integration_conflicts":
        raise AdapterError(f"Hay conflictos pendientes. Revisa {root / REPORT}; no se compilará una integración incompleta.")
    if report.get("adapter_digest") != current_digest:
        raise AdapterError("Cambió el adaptador. Vuelve a preparar el ZIP en otra carpeta.")
    # A user may edit a prepared tree deliberately (compile command), but
    # never silently substitute missing files or a partially copied checkout.
    for name in report.get("source_hashes", {}):
        if not (root / name).is_file():
            raise AdapterError(f"Falta un archivo preparado: {name}")
    return adapter, report


def run_logged(command: list[str], root: Path, env: dict, log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write("\n$ " + " ".join(command) + "\n")
        stream.flush()
        with subprocess.Popen(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", bufsize=1) as child:
            for line in child.stdout:
                print(line, end="", flush=True)
                stream.write(line)
            code = child.wait()
    if code:
        raise AdapterError(f"Falló {command[0]} (código {code}). Registro: {log}")


def package_keys(lock: bytes) -> set[tuple[str, str, str]]:
    return {(p["name"], p["version"], p.get("source", "")) for p in tomllib.loads(lock.decode())["package"]}


def ensure_locked(root: Path, report: dict, env: dict, log: Path) -> None:
    if report["lock_status"] != "needs_android_resolution":
        return
    before = (root / ".tablet/upstream-Cargo.lock").read_bytes()
    run_logged(["cargo", "metadata", "--format-version", "1"], root, env, log)
    removed = package_keys(before) - package_keys((root / "Cargo.lock").read_bytes())
    if removed:
        (root / ".tablet/rejected-Cargo.lock").write_bytes((root / "Cargo.lock").read_bytes())
        (root / "Cargo.lock").write_bytes(before)
        raise AdapterError("La resolución de Android sustituye dependencias originales. Se conservó el lock original; revisa .tablet/rejected-Cargo.lock.")
    report["lock_status"] = "resolved_preserving_upstream_packages"
    report["resolved_lock_sha256"] = file_sha(root / "Cargo.lock")
    git("add", "--", "Cargo.lock", cwd=root)
    write_json(root / REPORT, report)


def doctor(adapter: dict) -> list[str]:
    problems = []
    if sys.platform != "linux":
        problems.append("La compilación nativa requiere Linux x86_64; en Windows/macOS utiliza compilar-docker.")
    for name in ("git", "bash", "cargo", "rustup", "java", "keytool"):
        if not shutil.which(name):
            problems.append(f"Falta {name}.")
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk or not (Path(sdk) / "platforms/android-36/android.jar").is_file():
        problems.append("Configura ANDROID_HOME con la plataforma android-36.")
    if not sdk or not (Path(sdk) / "build-tools/36.0.0/apksigner").is_file():
        problems.append("Faltan Android build-tools 36.0.0.")
    ndk = os.environ.get("ANDROID_NDK_HOME")
    if not ndk or not (Path(ndk) / "toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip").is_file():
        problems.append("Configura ANDROID_NDK_HOME con NDK r28c o compatible.")
    if shutil.which("rustup"):
        result = subprocess.run(["rustup", "run", adapter["toolchain"]["rust"], "cargo", "--version"], capture_output=True)
        if result.returncode:
            problems.append(f"Instala Rust {adapter['toolchain']['rust']} (consulta LEEME.md).")
    return problems


def compile_prepared(root: Path, artifacts: Path, abi: str, keystore: Path | None,
                     ci: bool = False, kit: Path = KIT) -> dict:
    root, artifacts = root.resolve(), artifacts.resolve()
    adapter, report = load_prepared(root, kit)
    problems = doctor(adapter)
    if problems:
        raise AdapterError("\n".join(problems))
    if artifacts == root or root.is_relative_to(artifacts) or artifacts.is_relative_to(root):
        raise AdapterError("Usa una carpeta de resultados separada de la raíz del código fuente.")
    artifacts.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["RUSTUP_TOOLCHAIN"] = adapter["toolchain"]["rust"]
    env.setdefault("CARGO_BUILD_JOBS", "2")
    env.setdefault("CARGO_TARGET_DIR", str((kit / "cache/target").resolve()))
    env["CADCRAFT_ANDROID_OUTPUT"] = str(artifacts / "packaging")
    key = (keystore or Path(env.get("CADCRAFT_ANDROID_KEYSTORE", str(kit / "private/preview.keystore")))).resolve()
    key.parent.mkdir(parents=True, exist_ok=True)
    env["CADCRAFT_ANDROID_KEYSTORE"] = str(key)
    log = artifacts / "build.log"
    for field in ("apk", "apk_sha256", "symbols", "symbols_sha256", "error"):
        report.pop(field, None)
    report.update(status="building", physical_device_tested=False, ci_passed=False)
    write_json(root / REPORT, report)
    try:
        ensure_locked(root, report, env, log)
        if ci:
            run_logged(["cargo", "xtask", "ci"], root, env, log)
            run_logged(["cargo", "test", "--locked", "-p", "cadcraft-android", "--features", "desktop-preview", "--lib"], root, env, log)
            report["ci_passed"] = True
        run_logged(["bash", "packaging/android/build.sh", abi], root, env, log)
        apk_src = artifacts / "packaging" / f"CADCraft-Tablet-Preview-{abi}.apk"
        if not apk_src.is_file():
            raise AdapterError("La compilación no produjo la APK esperada.")
        apk = artifacts / f"CADCraft-Tablet-{report['upstream_version']}-{abi}.apk"
        shutil.copyfile(apk_src, apk)
        symbols = artifacts / f"CADCraft-Tablet-{report['upstream_version']}-{abi}-symbols.zip"
        lib = artifacts / "packaging/symbols" / abi / "libcadcraft_android.so"
        provenance = {"adapter_version": adapter["adapter_version"], "adapter_digest": report["adapter_digest"],
                      "source_zip_sha256": report["input_zip_sha256"], "upstream_version": report["upstream_version"],
                      "source_tree": tree_hashes(root), "apk_sha256": file_sha(apk), "abi": abi,
                      "physical_device_tested": False, "ci_passed": report.get("ci_passed", False)}
        with zipfile.ZipFile(symbols, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.write(lib, f"{abi}/libcadcraft_android.so")
            z.writestr("BUILD-INFO.json", json.dumps(provenance, indent=2) + "\n")
        report.update(status="compiled_not_device_tested", apk=str(apk), apk_sha256=file_sha(apk),
                      symbols=str(symbols), symbols_sha256=file_sha(symbols))
        write_json(artifacts / "BUILD-INFO.json", provenance)
    except (AdapterError, OSError) as exc:
        report.update(status="build_failed", error=str(exc))
        write_json(root / REPORT, report)
        raise
    write_json(root / REPORT, report)
    return report


def print_report(report: dict, output: Path) -> None:
    if report["conflicts"]:
        print(f"No se compiló: {len(report['conflicts'])} conflictos de integración.")
        for item in report["conflicts"]:
            print(f"  {item['path']}: {item['reason']}")
        print(f"Informe: {output / REPORT}")
    else:
        print(f"CadCraft Tablet {report['upstream_version']}: {report['status']}")
        print(f"Código generado: {output}")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Adaptador independiente: ZIP original de CadCraft → Android Tablet")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("prepare", "build"):
        item = sub.add_parser(command, help="Preparar sin compilar" if command == "prepare" else "Preparar y compilar la APK")
        item.add_argument("source_zip", type=Path)
        item.add_argument("--output", type=Path, default=KIT / "work/cadcraft")
        if command == "build":
            build_arguments(item)
    item = sub.add_parser("compile", help="Recompilar una carpeta preparada anteriormente")
    item.add_argument("prepared", type=Path)
    build_arguments(item)
    sub.add_parser("doctor", help="Comprobar requisitos de compilación nativa")
    return p


def build_arguments(item: argparse.ArgumentParser) -> None:
    item.add_argument("--artifacts", type=Path, default=KIT / "dist")
    item.add_argument("--abi", choices=("arm64-v8a", "x86_64"), default="arm64-v8a")
    item.add_argument("--keystore", type=Path)
    item.add_argument("--ci", action="store_true", help="Ejecutar CI de escritorio y pruebas de shell antes de empaquetar")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            adapter, _ = load_adapter(KIT)
            problems = doctor(adapter)
            print("\n".join(problems) if problems else "Herramientas de compilación disponibles.")
            return 1 if problems else 0
        if args.command in ("prepare", "build"):
            output = args.output.resolve()
            if args.command == "build" and output.exists():
                _, report = load_prepared(output)
                if report["input_zip_sha256"] != file_sha(args.source_zip):
                    raise AdapterError("La carpeta contiene otro ZIP. Selecciona un --output diferente.")
                # Reuse build artifacts, but never an unexpectedly edited source.
                current = tree_hashes(output)
                for name, expected in report["source_hashes"].items():
                    if name == "Cargo.lock" and report.get("resolved_lock_sha256"):
                        expected = report["resolved_lock_sha256"]
                    if current.get(name) != expected:
                        raise AdapterError(f"Cambió {name}. Usa 'compile' para compilar tus cambios, o prepara una carpeta nueva.")
                if current.keys() != report["source_hashes"].keys():
                    raise AdapterError("Cambió la lista de archivos preparados. Usa 'compile' para compilar tus cambios.")
            else:
                report = prepare(args.source_zip, output)
            print_report(report, output)
            if report["conflicts"]:
                return 2
            if args.command == "prepare":
                return 0
        else:
            output = args.prepared.resolve()
        report = compile_prepared(output, args.artifacts, args.abi, args.keystore, args.ci)
        print(f"APK: {report['apk']}\nSHA256: {report['apk_sha256']}\nSímbolos: {report['symbols']}")
        return 0
    except (AdapterError, OSError, ValueError, zipfile.BadZipFile, tomllib.TOMLDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
