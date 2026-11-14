"""Проверки установщика без сети и изменений системных каталогов."""

from io import BytesIO
from pathlib import Path
from subprocess import CalledProcessError
from tarfile import FilterError, TarInfo
from tarfile import open as open_tar
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch
from zipfile import ZipFile

import system


class SystemTests(TestCase):
    def test_user_and_wrong_distribution_are_rejected_before_apt(self):
        with (
            patch.object(system, "geteuid", return_value=1000),
            patch.object(system, "command") as command,
        ):
            self.assertEqual(system.main([]), 1)
            command.assert_not_called()
        with (
            patch.object(system, "geteuid", return_value=0),
            patch.object(
                system, "freedesktop_os_release", return_value={"ID": "debian"}
            ),
            patch.object(system, "command") as command,
        ):
            self.assertEqual(system.main([]), 1)
            command.assert_not_called()

    def test_apt_waits_for_dpkg_lock_and_stops_if_timeout_expires(self):
        with (
            patch.object(system, "validate_host", return_value="x86_64"),
            patch.object(
                system,
                "command",
                side_effect=[None, CalledProcessError(100, "apt-get")],
            ) as command,
            patch.object(system, "install_neovim") as install_neovim,
            patch.object(system, "link_binary") as link_binary,
            patch("builtins.print"),
        ):
            self.assertEqual(system.main([]), 1)
            self.assertEqual(command.call_args_list[0].args, ("apt-get", "update"))
            self.assertEqual(
                command.call_args_list[1].args,
                (
                    "apt-get",
                    "-o",
                    "DPkg::Lock::Timeout=600",
                    "install",
                    "-y",
                    *system.PACKAGES,
                ),
            )
            install_neovim.assert_not_called()
            link_binary.assert_not_called()

    def test_supported_architectures_and_rejection(self):
        with (
            patch.object(system, "geteuid", return_value=0),
            patch.object(
                system, "freedesktop_os_release", return_value={"ID": "ubuntu"}
            ),
        ):
            for name, expected in (("x86_64", "x86_64"), ("aarch64", "arm64")):
                with (
                    self.subTest(name=name),
                    patch.object(system, "machine", return_value=name),
                ):
                    self.assertEqual(system.validate_host(), expected)
            with (
                patch.object(system, "machine", return_value="riscv64"),
                self.assertRaises(ValueError),
            ):
                system.validate_host()

    def test_missing_or_ambiguous_asset_fails(self):
        with (
            patch.object(system, "read_json", return_value={"assets": []}),
            self.assertRaises(ValueError),
        ):
            system.release_asset("owner/repo", "file.zip")
        asset = {
            "name": "file.zip",
            "browser_download_url": "https://example.test/file",
        }
        with (
            patch.object(system, "read_json", return_value={"assets": [asset, asset]}),
            self.assertRaises(ValueError),
        ):
            system.release_asset("owner/repo", "file.zip")

    def test_lazygit_accepts_current_and_legacy_os_case_for_each_architecture(self):
        for arch in ("x86_64", "arm64"):
            for os_name in ("linux", "Linux"):
                with (
                    self.subTest(arch=arch, os_name=os_name),
                    TemporaryDirectory() as temporary,
                ):
                    work = Path(temporary)
                    binary_dir = work / "bin"
                    binary_dir.mkdir()
                    with open_tar(work / "lazygit.tar.gz", "w:gz") as output:
                        member = TarInfo("lazygit")
                        member.size = 4
                        output.addfile(member, BytesIO(b"test"))
                    url = "https://example.test/correct-archive"
                    assets = [
                        {
                            "name": f"lazygit_0.66.3_{os_name}_{arch}.tar.gz",
                            "browser_download_url": url,
                        },
                        {
                            "name": f"lazygit_0.66.3_darwin_{arch}.tar.gz",
                            "browser_download_url": "wrong-os",
                        },
                        {
                            "name": "lazygit_0.66.3_linux_32-bit.tar.gz",
                            "browser_download_url": "wrong-arch",
                        },
                    ]
                    with (
                        patch.object(
                            system,
                            "read_json",
                            return_value={"tag_name": "v0.66.3", "assets": assets},
                        ),
                        patch.object(system, "download") as download,
                        patch.object(system, "BIN", binary_dir),
                    ):
                        system.install_lazygit(work, arch)
                        download.assert_called_once_with(url, work / "lazygit.tar.gz")
                    self.assertEqual((binary_dir / "lazygit").read_bytes(), b"test")
                    self.assertEqual(
                        (binary_dir / "lazygit").stat().st_mode & 0o777, 0o755
                    )

    def test_tar_rejects_parent_traversal(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bad.tar.gz"
            with open_tar(archive, "w:gz") as output:
                member = TarInfo("../outside")
                member.size = 4
                output.addfile(member, BytesIO(b"oops"))
            with self.assertRaises(FilterError):
                system.extract_tar(archive, root / "extract")
            self.assertFalse((root / "outside").exists())

    def test_runtime_update_preserves_links_and_removes_old_files(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            (source / "bin").mkdir(parents=True)
            (source / "lib").mkdir()
            (source / "lib/npm.js").write_text("new npm")
            (source / "bin/npm").symlink_to("../lib/npm.js")
            destination = root / "node"
            destination.mkdir()
            (destination / "obsolete").write_text("old")
            with patch.object(system, "OPT", root):
                system.install_tree(source, destination)
                system.install_tree(source, destination)
            self.assertFalse((destination / "obsolete").exists())
            self.assertTrue((destination / "bin/npm").is_symlink())
            self.assertEqual((destination / "bin/npm").read_text(), "new npm")

    def test_binary_update_replaces_link_without_writing_through_it(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / "new"
            binary.write_bytes(b"new")
            previous = root / "old"
            previous.write_bytes(b"old")
            destination = root / "bin"
            destination.mkdir()
            (destination / "ya").symlink_to(previous)
            with patch.object(system, "BIN", destination):
                system.install_binary(binary, "ya")
            self.assertEqual(previous.read_bytes(), b"old")
            self.assertFalse((destination / "ya").is_symlink())
            self.assertEqual((destination / "ya").read_bytes(), b"new")

    def test_yazi_archives_install_both_binaries(self):
        for arch, target in (("x86_64", "x86_64"), ("arm64", "aarch64")):
            with self.subTest(arch=arch), TemporaryDirectory() as temporary:
                work = Path(temporary)
                binary_dir = work / "bin"
                binary_dir.mkdir()
                name = f"yazi-{target}-unknown-linux-musl"
                with ZipFile(work / "yazi.zip", "w") as output:
                    output.writestr(f"{name}/yazi", b"yazi")
                    output.writestr(f"{name}/ya", b"ya")
                with (
                    patch.object(
                        system, "release_asset", return_value="https://example.test/zip"
                    ),
                    patch.object(system, "download"),
                    patch.object(system, "BIN", binary_dir),
                ):
                    system.install_yazi(work, arch)
                self.assertEqual((binary_dir / "yazi").read_bytes(), b"yazi")
                self.assertEqual((binary_dir / "ya").read_bytes(), b"ya")


if __name__ == "__main__":
    main()
