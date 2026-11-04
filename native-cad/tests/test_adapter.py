"""Integration behaviour using the real adapter, without an SDK or network."""
from pathlib import Path
import hashlib
import importlib.util
import json
import stat
import subprocess
import tempfile
import tomllib
import unittest
from unittest import mock
import zipfile

KIT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tablet", KIT / "tablet.py")
tablet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tablet)


class AdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adapter, _ = tablet.load_adapter(KIT)
        cls.original = {p.relative_to(KIT / "integration/base").as_posix(): p.read_bytes()
                        for p in (KIT / "integration/base").rglob("*") if p.is_file()}
        cls.original.update({
            "crates/engine/Cargo.toml": b'[package]\nname="cadcraft-engine"\nversion="0.14.0"\n',
            "crates/ui-egui/Cargo.toml": b'[package]\nname="cadcraft-ui-egui"\nversion="0.14.0"\n',
            "README-unmodified.md": b"Original desktop documentation.\n",
        })

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.archive = self.root / "original.zip"
        self.output = self.root / "generated"

    def tearDown(self):
        self.temporary.cleanup()

    def make_zip(self, edits=None, remove=(), prefix="cadcraft-0.14.0/"):
        files = dict(self.original)
        files.update(edits or {})
        for name in remove:
            files.pop(name, None)
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in files.items():
                z.writestr(prefix + name, data)
        return files

    def test_exact_upstream_reproduces_every_integration_and_owned_file(self):
        self.make_zip()
        before = tablet.file_sha(self.archive)
        report = tablet.prepare(self.archive, self.output)
        self.assertEqual(report["status"], "prepared_not_compiled")
        self.assertEqual(report["lock_status"], "reviewed_0.14")
        self.assertFalse(report["physical_device_tested"])
        self.assertEqual(tablet.file_sha(self.archive), before)
        for item in self.adapter["modified"]:
            self.assertEqual(tablet.file_sha(self.output / item["path"]), item["tablet_sha256"], item["path"])
        for item in self.adapter["owned"]:
            self.assertEqual(tablet.file_sha(self.output / item["path"]), item["sha256"], item["path"])
        self.assertEqual((self.output / "README-unmodified.md").read_bytes(), self.original["README-unmodified.md"])
        tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=self.output).decode().split("\0"))
        self.assertTrue(set(report["source_hashes"]) <= tracked)
        self.assertFalse(any(name.startswith(".tablet/") for name in tracked))

    def test_zip_without_top_level_folder_is_supported(self):
        self.make_zip(prefix="")
        self.assertFalse(tablet.prepare(self.archive, self.output)["conflicts"])

    def test_independent_future_changes_and_version_are_preserved(self):
        manifest = self.original["Cargo.toml"].replace(b'"0.14.0"', b'"0.15.2"')
        chunks = self.original["Cargo.lock"].decode().split("[[package]]")
        for i in range(1, len(chunks)):
            package = tomllib.loads("[[package]]" + chunks[i])["package"][0]
            if not package.get("source") and package["version"] == "0.14.0":
                chunks[i] = chunks[i].replace('version = "0.14.0"', 'version = "0.15.2"', 1)
        lock = "[[package]]".join(chunks).encode()
        config = b"# Independently added by future desktop release\n" + self.original[".cargo/config.toml"]
        self.make_zip({"Cargo.toml": manifest, "Cargo.lock": lock, ".cargo/config.toml": config,
                       "new-desktop-feature.rs": b"// future upstream feature\n"})
        report = tablet.prepare(self.archive, self.output)
        self.assertFalse(report["conflicts"])
        self.assertFalse(report["exact_base"])
        self.assertEqual(report["upstream_version"], "0.15.2")
        self.assertEqual(report["android_version_code"], 15002)
        self.assertEqual(report["lock_status"], "needs_android_resolution")
        self.assertEqual((self.output / "Cargo.lock").read_bytes(), lock)
        self.assertIn(b"Independently added", (self.output / ".cargo/config.toml").read_bytes())
        self.assertIn(b"build-id=sha1", (self.output / ".cargo/config.toml").read_bytes())
        self.assertEqual((self.output / "new-desktop-feature.rs").read_bytes(), b"// future upstream feature\n")
        android = (self.output / "packaging/android/AndroidManifest.xml").read_text()
        self.assertIn('android:versionName="0.15.2"', android)
        self.assertIn('android:versionCode="15002"', android)

    def test_overlapping_change_keeps_desktop_and_blocks_compilation(self):
        name = "crates/engine/src/undoctl.rs"
        changed = self.original[name].replace(b"MAX_UNDO: usize = 2000", b"MAX_UNDO: usize = 500")
        self.make_zip({name: changed})
        report = tablet.prepare(self.archive, self.output)
        self.assertEqual(report["status"], "integration_conflicts")
        self.assertIn(name, {c["path"] for c in report["conflicts"]})
        self.assertEqual((self.output / name).read_bytes(), changed)
        self.assertIn(b"<<<<<<< desktop", (self.output / ".tablet/conflicts" / (name + ".merge")).read_bytes())
        with self.assertRaisesRegex(tablet.AdapterError, "conflictos pendientes"):
            tablet.load_prepared(self.output)

    def test_renamed_or_removed_shared_module_is_reported(self):
        name = "crates/engine/src/undoctl.rs"
        self.make_zip({"crates/engine/src/undoctl_new.rs": self.original[name]}, remove=(name,))
        report = tablet.prepare(self.archive, self.output)
        self.assertIn(name, {c["path"] for c in report["conflicts"]})
        self.assertFalse((self.output / name).exists())

    def test_new_upstream_file_cannot_be_overwritten_by_owned_file(self):
        name = "crates/ui-egui/src/tablet.rs"
        self.make_zip({name: b"// desktop introduces its own tablet integration\n"})
        report = tablet.prepare(self.archive, self.output)
        self.assertIn(name, {c["path"] for c in report["conflicts"]})
        self.assertTrue((self.output / name).read_bytes().startswith(b"// desktop introduces"))

    def test_existing_output_and_user_edits_are_never_replaced(self):
        self.make_zip()
        self.output.mkdir()
        (self.output / "my-work.txt").write_text("keep me")
        with self.assertRaisesRegex(tablet.AdapterError, "Ya existe"):
            tablet.prepare(self.archive, self.output)
        self.assertEqual((self.output / "my-work.txt").read_text(), "keep me")

    def test_path_traversal_absolute_windows_and_reserved_names_are_rejected(self):
        for name in ("../escape", "/tmp/escape", "C:/escape", "a\\escape", "root/../escape", "root/.git/config", "root/.tablet/report.json", "CON.txt"):
            with self.subTest(name=name):
                self.make_zip({name: b"bad"}, prefix="")
                with self.assertRaises(tablet.AdapterError):
                    tablet.prepare(self.archive, self.output)
                self.assertFalse(self.output.exists())
        self.assertFalse((self.root / "escape").exists())

    def test_symbolic_links_are_rejected_before_extraction(self):
        self.make_zip()
        with zipfile.ZipFile(self.archive, "a") as z:
            item = zipfile.ZipInfo("cadcraft-0.14.0/symlink")
            item.create_system = 3
            item.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(item, "../../outside")
        with self.assertRaisesRegex(tablet.AdapterError, "enlace"):
            tablet.prepare(self.archive, self.output)
        self.assertFalse(self.output.exists())

    def test_case_insensitive_duplicates_are_rejected(self):
        self.make_zip({"readme-UNMODIFIED.md": b"duplicate"})
        with self.assertRaisesRegex(tablet.AdapterError, "repetida"):
            tablet.prepare(self.archive, self.output)

    def test_extraction_limit_is_enforced_before_output_is_installed(self):
        self.make_zip()
        with mock.patch.object(tablet, "MAX_TOTAL", 100):
            with self.assertRaisesRegex(tablet.AdapterError, "límite"):
                tablet.prepare(self.archive, self.output)
        self.assertFalse(self.output.exists())

    def test_binary_distribution_zip_is_not_treated_as_source(self):
        with zipfile.ZipFile(self.archive, "w") as z:
            z.writestr("cadcraft.exe", b"not source")
        with self.assertRaisesRegex(tablet.AdapterError, "código fuente original"):
            tablet.prepare(self.archive, self.output)

    def test_already_adapted_tablet_zip_is_not_a_fresh_upstream_input(self):
        self.make_zip({"apps/cadcraft-android/Cargo.toml": b'[package]\nname="cadcraft-android"\n'})
        with self.assertRaisesRegex(tablet.AdapterError, "ya incluye"):
            tablet.prepare(self.archive, self.output)

    def test_bad_adapter_hash_fails_before_reading_archive_contents(self):
        self.make_zip()
        with mock.patch.object(tablet, "sha", return_value="bad"):
            with self.assertRaisesRegex(tablet.AdapterError, "hashes"):
                tablet.prepare(self.archive, self.output)

    def test_prerelease_and_unrepresentable_version_stop_with_clear_error(self):
        for version in ("0.15.0-beta1", "0.14.1000", "5000.0.0"):
            with self.subTest(version=version):
                self.make_zip({"Cargo.toml": self.original["Cargo.toml"].replace(b'"0.14.0"', json.dumps(version).encode())})
                with self.assertRaises(tablet.AdapterError):
                    tablet.prepare(self.archive, self.output)
                self.assertFalse(self.output.exists())

    def test_future_lock_resolution_may_add_but_not_replace_desktop_packages(self):
        self.make_zip()
        report = tablet.prepare(self.archive, self.output)
        report["lock_status"] = "needs_android_resolution"
        original = (self.output / ".tablet/upstream-Cargo.lock").read_bytes()
        (self.output / "Cargo.lock").write_bytes(original)

        def minimal_resolution(*args):
            (self.output / "Cargo.lock").write_bytes(original + b'\n[[package]]\nname = "new-android-only"\nversion = "1.0.0"\n')

        with mock.patch.object(tablet, "run_logged", side_effect=minimal_resolution):
            tablet.ensure_locked(self.output, report, {}, self.root / "build.log")
        self.assertEqual(report["lock_status"], "resolved_preserving_upstream_packages")
        self.assertTrue(tablet.package_keys(original) <= tablet.package_keys((self.output / "Cargo.lock").read_bytes()))

    def test_lock_replacement_is_rejected_and_original_restored(self):
        self.make_zip()
        report = tablet.prepare(self.archive, self.output)
        report["lock_status"] = "needs_android_resolution"
        original = (self.output / ".tablet/upstream-Cargo.lock").read_bytes()

        def invalid_resolution(*args):
            (self.output / "Cargo.lock").write_bytes(b'version=4\n[[package]]\nname="other"\nversion="1.0.0"\n')

        with mock.patch.object(tablet, "run_logged", side_effect=invalid_resolution):
            with self.assertRaisesRegex(tablet.AdapterError, "sustituye dependencias"):
                tablet.ensure_locked(self.output, report, {}, self.root / "build.log")
        self.assertEqual((self.output / "Cargo.lock").read_bytes(), original)
        self.assertTrue((self.output / ".tablet/rejected-Cargo.lock").is_file())

    def test_packaging_workflow_retains_symbols_and_records_exact_artifact_hash(self):
        self.make_zip()
        tablet.prepare(self.archive, self.output)
        artifacts = self.root / "dist"
        key = self.root / "private/key.keystore"

        def package(command, root, env, log):
            self.assertEqual(command[:2], ["bash", "packaging/android/build.sh"])
            self.assertEqual(env["CADCRAFT_ANDROID_KEYSTORE"], str(key))
            stage = Path(env["CADCRAFT_ANDROID_OUTPUT"])
            stage.mkdir(parents=True)
            (stage / "CADCraft-Tablet-Preview-arm64-v8a.apk").write_bytes(b"unit-test-artifact")
            lib = stage / "symbols/arm64-v8a/libcadcraft_android.so"
            lib.parent.mkdir(parents=True)
            lib.write_bytes(b"unit-test-symbols")

        with mock.patch.object(tablet, "doctor", return_value=[]), mock.patch.object(tablet, "run_logged", side_effect=package):
            report = tablet.compile_prepared(self.output, artifacts, "arm64-v8a", key)
        self.assertEqual(report["status"], "compiled_not_device_tested")
        self.assertEqual(report["apk_sha256"], hashlib.sha256(b"unit-test-artifact").hexdigest())
        with zipfile.ZipFile(report["symbols"]) as z:
            self.assertEqual(z.read("arm64-v8a/libcadcraft_android.so"), b"unit-test-symbols")
            info = json.loads(z.read("BUILD-INFO.json"))
            self.assertFalse(info["physical_device_tested"])
            self.assertFalse(info["ci_passed"])

    def test_packaging_failure_does_not_report_success(self):
        self.make_zip()
        previous = tablet.prepare(self.archive, self.output)
        previous.update(ci_passed=True, apk="previous.apk", apk_sha256="old")
        tablet.write_json(self.output / tablet.REPORT, previous)
        with mock.patch.object(tablet, "doctor", return_value=[]), mock.patch.object(tablet, "run_logged", side_effect=tablet.AdapterError("compiler failed")):
            with self.assertRaisesRegex(tablet.AdapterError, "compiler failed"):
                tablet.compile_prepared(self.output, self.root / "dist", "arm64-v8a", None)
        report = json.loads((self.output / tablet.REPORT).read_text())
        self.assertEqual(report["status"], "build_failed")
        self.assertNotIn("apk", report)
        self.assertFalse(report["ci_passed"])

    def test_artifacts_cannot_recurse_into_the_source_staging_tree(self):
        self.make_zip()
        tablet.prepare(self.archive, self.output)
        with mock.patch.object(tablet, "doctor", return_value=[]):
            with self.assertRaisesRegex(tablet.AdapterError, "separada"):
                tablet.compile_prepared(self.output, self.output / "outputs", "arm64-v8a", None)


if __name__ == "__main__":
    unittest.main()
