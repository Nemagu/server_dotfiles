"""Проверки пользовательских операций без установки и изменения оболочки."""

from pathlib import Path
from subprocess import CalledProcessError
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

import setup


class SetupTests(TestCase):
    def test_root_is_rejected_but_help_is_available(self):
        with (
            patch.object(setup, "geteuid", return_value=0),
            patch.object(setup, "command") as command,
            patch("builtins.print"),
        ):
            self.assertEqual(setup.main(["tools"]), 1)
            self.assertEqual(setup.main(["help"]), 0)
            command.assert_not_called()

    def test_stow_conflict_prevents_restow(self):
        with (
            patch.object(setup, "need"),
            patch.object(
                setup, "command", side_effect=CalledProcessError(1, "stow")
            ) as command,
        ):
            with self.assertRaises(CalledProcessError):
                setup.link_configs()
            self.assertEqual(command.call_count, 1)
            self.assertIn("--simulate", command.call_args.args)

    def test_checkout_refuses_non_repository_directory(self):
        with (
            TemporaryDirectory() as temporary,
            patch.object(setup, "command") as command,
        ):
            with self.assertRaises(RuntimeError):
                setup.checkout(
                    "https://example.test/repo", Path(temporary), update=True
                )
            command.assert_not_called()

    def test_checkout_updates_with_fast_forward_only(self):
        with (
            TemporaryDirectory() as temporary,
            patch.object(setup, "command") as command,
        ):
            directory = Path(temporary)
            (directory / ".git").mkdir()
            setup.checkout("https://example.test/repo", directory, update=True)
            command.assert_called_once_with(
                "git", "-C", str(directory), "pull", "--ff-only"
            )

    def test_existing_uv_needs_no_download(self):
        with (
            patch.object(setup, "which", return_value="/usr/bin/uv"),
            patch.object(setup, "download") as download,
            patch.object(setup, "command") as command,
        ):
            setup.install_uv()
            download.assert_not_called()
            command.assert_not_called()

    def test_tools_preserve_existing_codebook_and_bat_theme(self):
        with (
            patch.object(setup, "need"),
            patch.object(setup, "which", return_value="/usr/bin/codebook-lsp"),
            patch.object(setup, "download") as download,
            patch.object(
                setup, "command", return_value="Catppuccin Frappe\n"
            ) as command,
        ):
            setup.install_tools()
            download.assert_not_called()
            calls = [call.args for call in command.call_args_list]
            self.assertIn(("uv", "tool", "install", "basedpyright"), calls)
            self.assertIn(("uv", "tool", "install", "ruff"), calls)
            self.assertFalse(any(args[0] == "cargo" for args in calls))

    def test_shell_rejects_unregistered_path_and_preserves_password_prompt(self):
        with (
            patch.object(setup, "need", return_value="/usr/bin/zsh"),
            patch.object(Path, "read_text", return_value="/bin/bash\n"),
            patch.object(setup, "command") as command,
        ):
            with self.assertRaises(RuntimeError):
                setup.change_shell()
            command.assert_not_called()
        with (
            patch.object(setup, "need", return_value="/usr/bin/zsh"),
            patch.object(Path, "read_text", return_value="/usr/bin/zsh\n"),
            patch.object(setup, "command") as command,
        ):
            setup.change_shell()
            command.assert_called_once_with("chsh", "-s", "/usr/bin/zsh")

    def test_missing_commands_make_check_fail_without_running_them(self):
        with (
            patch.object(setup, "which", return_value=None),
            patch.object(setup, "command") as command,
            patch("builtins.print"),
        ):
            with self.assertRaises(RuntimeError):
                setup.check()
            command.assert_not_called()

    def test_update_does_not_reinstall_system_codebook_or_update_system_uv(self):
        with (
            patch.object(setup, "install_rust"),
            patch.object(setup, "install_uv"),
            patch.object(setup, "install_tools"),
            patch.object(setup, "link_configs"),
            patch.object(setup, "install_plugins") as plugins,
            patch.object(setup, "check"),
            patch.object(setup, "need", return_value="/usr/bin/uv"),
            patch.object(
                setup, "command", return_value="unrelated v1.0.0:\n"
            ) as command,
        ):
            setup.update()
            plugins.assert_called_once_with(update=True)
            calls = [call.args for call in command.call_args_list]
            self.assertNotIn(("uv", "self", "update"), calls)
            self.assertNotIn(
                ("cargo", "+stable", "install", "--locked", "codebook-lsp"), calls
            )


if __name__ == "__main__":
    main()
