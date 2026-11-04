"""Regressions for automatic downloads and isolated native build orchestration."""
from pathlib import Path
import io
import json
import os
import sys
import tempfile
import unittest
import subprocess
import contextlib
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import linux


class LinuxBuilderTest(unittest.TestCase):
    def test_incompatible_java_target_stops_before_source_download_or_rust_build(self):
        errors = io.StringIO()
        results = [
            subprocess.CompletedProcess([], 0, stdout=b"javac 27", stderr=b""),
            subprocess.CompletedProcess([], 0, stdout="", stderr='openjdk version "27"'),
            subprocess.CompletedProcess([], 2, stdout="", stderr="error: release version 17 not supported"),
        ]
        with mock.patch.object(linux.shutil, "which", return_value="/usr/bin/tool"), \
             mock.patch.object(linux.subprocess, "run", side_effect=results), \
             mock.patch.object(linux, "download_source") as download, \
             contextlib.redirect_stderr(errors):
            self.assertEqual(linux.main(["--version", "0.15.1"]), 1)
        download.assert_not_called()
        self.assertIn("JDK actual no puede compilar para Java 17", errors.getvalue())

    def test_latest_release_resolves_to_an_immutable_commit_and_reuses_verified_zip(self):
        commit = "a" * 40
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(linux, "metadata", side_effect=[
                {"tag_name": "v0.15.1"}, {"sha": commit},
                {"tag_name": "v0.15.1"}, {"sha": commit},
            ]) as metadata, mock.patch.object(linux, "open_url", return_value=io.BytesIO(b"source zip")) as download:
                archive, tag, resolved = linux.download_source(Path(temporary))
                self.assertEqual((tag, resolved), ("v0.15.1", commit))
                self.assertEqual(archive.read_bytes(), b"source zip")
                self.assertEqual(linux.download_source(Path(temporary)), (archive, tag, resolved))
                download.assert_called_once_with("https://codeload.github.com/storytold/cadcraft/zip/" + commit)
                self.assertEqual(metadata.call_args_list[1].args, ("commits/v0.15.1",))

    def test_corrupt_cache_is_downloaded_again(self):
        commit = "b" * 40
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            archive = cache / ("cadcraft-" + commit + ".zip")
            archive.write_bytes(b"corrupted")
            archive.with_suffix(".json").write_text(json.dumps({"commit": commit, "sha256": "wrong"}))
            with mock.patch.object(linux, "metadata", return_value={"sha": commit}), \
                 mock.patch.object(linux, "open_url", return_value=io.BytesIO(b"correct")):
                linux.download_source(cache, "0.15.1")
            self.assertEqual(archive.read_bytes(), b"correct")
            self.assertFalse(archive.with_suffix(".part").exists())

    def test_interrupted_download_does_not_replace_existing_archive(self):
        commit = "c" * 40
        response = mock.MagicMock()
        response.__enter__.return_value.read.side_effect = [b"partial", OSError("connection closed")]
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            archive = cache / ("cadcraft-" + commit + ".zip")
            archive.write_bytes(b"previous")
            with mock.patch.object(linux, "metadata", return_value={"sha": commit}), \
                 mock.patch.object(linux, "open_url", return_value=response):
                with self.assertRaises(OSError):
                    linux.download_source(cache, "0.15.1")
            self.assertEqual(archive.read_bytes(), b"previous")
            self.assertFalse(archive.with_suffix(".part").exists())

    def test_source_selector_rejects_unexpected_tags_and_urls(self):
        for tag in (None, "main", "v0.15.1-beta", "../main", "０.１５.１"):
            with self.subTest(tag=tag), self.assertRaises(linux.BuilderError):
                linux.stable_tag(tag)
        for url in ("http://github.com/a", "https://github.com.example.com/a",
                    "https://user@github.com/a", "https://github.com:444/a", "file:///tmp/a"):
            with self.subTest(url=url), self.assertRaises(linux.BuilderError):
                linux.validate_url(url)

    def test_incompatible_external_rust_flags_do_not_reach_compilation(self):
        with tempfile.TemporaryDirectory() as temporary, \
             mock.patch.dict(os.environ, {"RUSTFLAGS": "-C prefer-dynamic", "RUSTC_WRAPPER": "/missing", "HOME": "/original-home"}):
            env = linux.build_env(Path(temporary), 3)
            with linux.environment(env):
                self.assertNotIn("RUSTFLAGS", os.environ)
                self.assertNotIn("RUSTC_WRAPPER", os.environ)
                self.assertEqual(os.environ["CARGO_BUILD_JOBS"], "3")
                self.assertEqual(os.environ["HOME"], "/original-home")
            self.assertEqual(os.environ["RUSTFLAGS"], "-C prefer-dynamic")

    def test_build_failure_restores_callers_environment(self):
        original = os.environ.copy()
        with self.assertRaises(RuntimeError):
            with linux.environment({"ONLY_FOR_BUILDER": "yes"}):
                self.assertEqual(dict(os.environ), {"ONLY_FOR_BUILDER": "yes"})
                raise RuntimeError("failed")
        self.assertEqual(dict(os.environ), original)


if __name__ == "__main__":
    unittest.main()
