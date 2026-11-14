"""Пользовательская настройка dotfiles средствами стандартной библиотеки."""

from argparse import ArgumentParser
from os import environ, geteuid
from pathlib import Path
from shlex import join
from shutil import which
from subprocess import CalledProcessError, run
from tempfile import TemporaryDirectory

from system import download

ROOT = Path(__file__).resolve().parent.parent
HOME = Path.home()
COMMANDS = [
    "git",
    "make",
    "stow",
    "zsh",
    "tmux",
    "nvim",
    "bat",
    "btop",
    "lazygit",
    "yazi",
    "ya",
    "fzf",
    "rg",
    "fd",
    "zoxide",
    "file",
    "jq",
    "curl",
    "unzip",
    "tar",
    "cc",
    "python3",
    "node",
    "npm",
    "rustup",
    "cargo",
    "rust-analyzer",
    "uv",
    "basedpyright-langserver",
    "ruff",
    "codebook-lsp",
]


def command(
    *args: str, capture: bool = False, env: dict[str, str] | None = None
) -> str:
    """Запускает команду без shell и возвращает запрошенный вывод."""
    print(f"+ {join(args)}", flush=True)
    result = run(args, check=True, text=True, capture_output=capture, env=env)
    return result.stdout or ""


def need(name: str) -> str:
    path = which(name)
    if path is None:
        raise RuntimeError(f"Missing command: {name}")
    return path


def install_rust() -> None:
    if which("rustup") is None:
        with TemporaryDirectory(prefix="dotfiles-rust-") as temporary:
            installer = Path(temporary) / "rustup.sh"
            download("https://sh.rustup.rs", installer)
            command(
                "sh", str(installer), "-y", "--profile", "minimal", "--no-modify-path"
            )
    command("rustup", "toolchain", "install", "stable", "--profile", "minimal")
    command(
        "rustup",
        "component",
        "add",
        "--toolchain",
        "stable",
        "rust-analyzer",
        "rust-src",
        "rustfmt",
        "clippy",
    )


def install_uv() -> None:
    if which("uv") is None:
        with TemporaryDirectory(prefix="dotfiles-uv-") as temporary:
            installer = Path(temporary) / "uv.sh"
            download("https://astral.sh/uv/install.sh", installer)
            command("sh", str(installer), env={**environ, "UV_NO_MODIFY_PATH": "1"})


def install_tools() -> None:
    need("uv")
    need("cargo")
    need("bat")
    command("uv", "tool", "install", "basedpyright")
    command("uv", "tool", "install", "ruff")
    env = {**environ, "BAT_CONFIG_PATH": str(ROOT / ".config/bat/config")}
    themes = command("bat", "--list-themes", capture=True, env=env).splitlines()
    if "Catppuccin Frappe" not in themes:
        theme = HOME / ".config/bat/themes/Catppuccin Frappe.tmTheme"
        theme.parent.mkdir(parents=True, exist_ok=True)
        download(
            "https://raw.githubusercontent.com/catppuccin/bat/main/themes/"
            "Catppuccin%20Frappe.tmTheme",
            theme,
        )
        command("bat", "cache", "--build", env=env)
    if which("codebook-lsp") is None:
        command("cargo", "+stable", "install", "--locked", "codebook-lsp")


def checkout(url: str, destination: Path, *, update: bool) -> None:
    """Клонирует внешний плагин или обновляет существующий без merge-коммита."""
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        command("git", "clone", url, str(destination))
    elif not (destination / ".git").exists():
        raise RuntimeError(f"Existing directory is not a Git checkout: {destination}")
    if update:
        command("git", "-C", str(destination), "pull", "--ff-only")


def install_plugins(*, update: bool = False) -> None:
    need("git")
    need("ya")
    zsh = HOME / ".config/zsh/oh-my-zsh"
    checkout("https://github.com/ohmyzsh/ohmyzsh.git", zsh, update=update)
    checkout(
        "https://github.com/Aloxaf/fzf-tab.git",
        zsh / "custom/plugins/fzf-tab",
        update=update,
    )
    for plugin in (
        "zsh-autosuggestions",
        "zsh-syntax-highlighting",
        "zsh-history-substring-search",
    ):
        checkout(
            f"https://github.com/zsh-users/{plugin}.git",
            zsh / "custom/plugins" / plugin,
            update=update,
        )
    for plugin in ("tpm", "tmux-sensible"):
        checkout(
            f"https://github.com/tmux-plugins/{plugin}.git",
            HOME / ".config/tmux/plugins" / plugin,
            update=update,
        )
    command("ya", "pkg", "upgrade" if update else "install")


def link_configs() -> None:
    """Применяет ссылки Stow только после успешной проверки конфликтов."""
    need("stow")
    args = (
        "stow",
        "--no-folding",
        f"--dir={ROOT.parent}",
        f"--target={HOME}",
    )
    command(*args, "--simulate", "--verbose", ROOT.name)
    command(*args, "--restow", "--verbose", ROOT.name)


def change_shell() -> None:
    zsh = need("zsh")
    need("chsh")
    if zsh not in Path("/etc/shells").read_text().splitlines():
        raise RuntimeError(
            f"{zsh} is not listed in /etc/shells; ask root to register it."
        )
    command("chsh", "-s", zsh)


def check() -> None:
    """Проверяет доступные команды и конфиги без установки компонентов."""
    failed = False
    for name in COMMANDS:
        present = which(name) is not None
        print(f"{'OK     ' if present else 'MISSING'} {name}")
        if not present:
            failed = True
    if which("zsh") is not None:
        directory = ROOT / ".config/zsh"
        sources = [directory / name for name in (".zshenv", ".zprofile", ".zshrc")]
        sources.extend(sorted((directory / "functions").glob("*")))
        sources.extend(sorted((directory / "fzf_themes").glob("*.sh")))
        for source in sources:
            try:
                command("zsh", "-n", str(source))
            except CalledProcessError:
                failed = True
    if which("bat") is not None:
        env = {**environ, "BAT_CONFIG_PATH": str(ROOT / ".config/bat/config")}
        themes = command("bat", "--list-themes", capture=True, env=env).splitlines()
        if "Catppuccin Frappe" not in themes:
            print("MISSING bat theme: Catppuccin Frappe")
            failed = True
    if failed:
        raise RuntimeError("Dependency or configuration checks failed.")


def update() -> None:
    install_rust()
    install_uv()
    if need("uv") == str(HOME / ".local/bin/uv"):
        command("uv", "self", "update")
    install_tools()
    command("uv", "tool", "upgrade", "basedpyright", "ruff")
    installed = command("cargo", "install", "--list", capture=True).splitlines()
    if any(line.startswith("codebook-lsp ") for line in installed):
        command("cargo", "+stable", "install", "--locked", "codebook-lsp")
    link_configs()
    install_plugins(update=True)
    check()


def show_help() -> None:
    """Печатает подробную справку всех целей Make без побочных эффектов."""
    print(Path(__file__).with_name("help.txt").read_text(), end="")


def main(argv: list[str] | None = None) -> int:
    actions = {
        "help": show_help,
        "rust": install_rust,
        "uv": install_uv,
        "tools": install_tools,
        "plugins": install_plugins,
        "link": link_configs,
        "shell": change_shell,
        "check": check,
        "update": update,
    }
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=actions)
    args = parser.parse_args(argv)
    if args.action == "help":
        show_help()
        return 0
    if geteuid() == 0:
        print(
            "Run user targets without root privileges; use make system for system tools."
        )
        return 1
    environ["PATH"] = (
        f"{HOME / '.local/bin'}:{HOME / '.cargo/bin'}:{environ.get('PATH', '')}"
    )
    try:
        actions[args.action]()
    except (OSError, RuntimeError, CalledProcessError) as error:
        print(f"Setup failed: {error}")
        if isinstance(error, CalledProcessError) and error.stderr:
            print(error.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
