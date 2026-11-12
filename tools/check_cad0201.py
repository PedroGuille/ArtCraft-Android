#!/usr/bin/env python3
"""Check the reviewed CADCraft 0.20.1 sources without producing an APK."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "native-cad"
COMMIT = "7526dc62c14e71b3c8d46e73bbf1fa29ef506af1"
PROFILE = "release-0.20.1"
spec = importlib.util.spec_from_file_location("tablet", KIT / "tablet.py")
tablet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tablet)


def verify(archive, output):
    report = tablet.prepare(archive, output, KIT)
    assert report["upstream_version"] == "0.20.1", report
    assert report.get("source_profile") == PROFILE and not report["conflicts"], report
    manifest = (output / "packaging/android/AndroidManifest.xml").read_text()
    assert 'android:versionName="0.20.1"' in manifest
    assert 'android:versionCode="20001"' in manifest
    adapter = json.loads((KIT / "adapter.json").read_text())
    profile = next(p for p in adapter["source_profiles"] if p["id"] == PROFILE)
    assert profile["source_commit"] == COMMIT
    for record in profile["files"]:
        assert tablet.file_sha(output / record["path"]) == record["sha256"], record["path"]
    return report


def reject_changed_inputs(archive, work):
    # Check both a future release and same-version changes in the resolved conflict.
    for label, path, old, new in (
        ("future", "Cargo.toml", b'version = "0.20.1"', b'version = "0.20.2"'),
        ("changed-close", "crates/ui-egui/src/closing.rs", b"Answer the Save dialog first.", b"Changed upstream save guard."),
    ):
        changed = work / (label + ".zip")
        replaced = False
        with zipfile.ZipFile(archive) as source, zipfile.ZipFile(changed, "w", zipfile.ZIP_DEFLATED) as dest:
            manifest = min((n for n in source.namelist() if n.endswith("Cargo.toml")), key=lambda n: n.count("/"))
            prefix = manifest[:-len("Cargo.toml")]
            for item in source.infolist():
                data = source.read(item)
                if item.filename == prefix + path:
                    assert old in data, path
                    data = data.replace(old, new, 1)
                    replaced = True
                dest.writestr(item, data)
        assert replaced, path
        report = tablet.prepare(changed, work / label, KIT)
        assert "source_profile" not in report, report
        assert report["status"] == "integration_conflicts" and report["conflicts"], report


def check_android(source, report, work):
    env = os.environ.copy()
    ndk = Path(env["ANDROID_NDK_HOME"])
    llvm = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    assert (llvm / "aarch64-linux-android26-clang").is_file(), ndk
    env.update(
        CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=str(llvm / "aarch64-linux-android26-clang"),
        CC_aarch64_linux_android=str(llvm / "aarch64-linux-android26-clang"),
        CXX_aarch64_linux_android=str(llvm / "aarch64-linux-android26-clang++"),
        AR_aarch64_linux_android=str(llvm / "llvm-ar"),
        CARGO_NET_GIT_FETCH_WITH_CLI="true",
        GIT_TERMINAL_PROMPT="0",
    )
    tablet.ensure_locked(source, report, env, work / "resolve.log")
    bridge = source / "packaging/android/prepare_winit.py"
    workspace = subprocess.check_output(
        ["python3", str(bridge), str(work / "hover")], cwd=source, env=env, text=True,
    ).strip()
    subprocess.run(
        ["cargo", "check", "--locked", "--target", "aarch64-linux-android", "--lib", "-p", "cadcraft-android"],
        cwd=workspace, env=env, check=True,
    )
    # The closing regressions run headlessly on the host, including the new desktop dialog case.
    subprocess.run(
        ["cargo", "test", "--locked", "-p", "cadcraft-ui-egui", "closing::tests::", "--lib"],
        cwd=source, env=env, check=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Unmodified source ZIP for the v0.20.1 tag")
    parser.add_argument("--check-android", action="store_true", help="Also check ARM64 types and run closing tests; requires Rust and NDK")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cad0201-check-") as temporary:
        work = Path(temporary)
        source = work / "reviewed"
        report = verify(args.archive, source)
        reject_changed_inputs(args.archive, work)
        print("CADCraft 0.20.1 integration and changed-input guards passed.", flush=True)
        if args.check_android:
            check_android(source, report, work)
    print("Source checks passed. No APK generated.", flush=True)


if __name__ == "__main__":
    main()
