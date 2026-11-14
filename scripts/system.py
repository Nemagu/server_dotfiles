"""Установка системных утилит Ubuntu без сторонних Python-пакетов."""

from argparse import ArgumentParser
from json import load
from os import environ, geteuid
from pathlib import Path
from platform import freedesktop_os_release, machine
from shlex import join
from shutil import copy2, copyfileobj, copytree
from subprocess import CalledProcessError, run
from tarfile import TarError
from tarfile import open as open_tar
from tempfile import TemporaryDirectory
from typing import Any
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

PACKAGES = (
    "git",
    "make",
    "stow",
    "zsh",
    "tmux",
    "bat",
    "btop",
    "ripgrep",
    "fd-find",
    "zoxide",
    "file",
    "jq",
    "curl",
    "ca-certificates",
    "unzip",
    "tar",
    "xz-utils",
    "build-essential",
    "pkg-config",
    "libssl-dev",
    "python3",
    "python3-venv",
)
BIN = Path("/usr/local/bin")
OPT = Path("/opt")


def command(*args: str) -> None:
    """Запускает команду и останавливает установку при ошибке."""
    print(f"+ {join(args)}", flush=True)
    run(args, check=True, env={**environ, "DEBIAN_FRONTEND": "noninteractive"})


def read_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": "server-dotfiles"})
    with urlopen(request, timeout=60) as response:
        return load(response)


def download(url: str, destination: Path) -> None:
    print(f"Download: {url}", flush=True)
    request = Request(url, headers={"User-Agent": "server-dotfiles"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as output:
        copyfileobj(response, output)


def release_asset(repo: str, name: str) -> str:
    """Находит ровно один файл в актуальном стабильном релизе."""
    release = read_json(f"https://api.github.com/repos/{repo}/releases/latest")
    matches = [
        asset["browser_download_url"]
        for asset in release["assets"]
        if asset["name"] == name
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one release asset: {repo}/{name}")
    return matches[0]


def extract_tar(archive: Path, destination: Path) -> None:
    """Распаковывает архив с запретом небезопасных путей и ссылок."""
    destination.mkdir()
    with open_tar(archive) as source:
        source.extractall(destination, filter="data")


def install_binary(source: Path, name: str) -> None:
    destination = BIN / name
    if destination.is_symlink():
        destination.unlink()
    copy2(source, destination)
    destination.chmod(0o755)


def link_binary(target: Path, name: str) -> None:
    destination = BIN / name
    if destination.is_dir():
        raise ValueError(f"Cannot replace directory: {destination}")
    destination.unlink(missing_ok=True)
    destination.symlink_to(target)


def install_tree(source: Path, destination: Path) -> None:
    """Заменяет runtime целиком, сохраняя внутренние символические ссылки."""
    with TemporaryDirectory(prefix=".server-dotfiles-", dir=OPT) as temporary:
        staging = Path(temporary) / "new"
        previous = Path(temporary) / "previous"
        copytree(source, staging, symlinks=True)
        if destination.exists() or destination.is_symlink():
            destination.rename(previous)
        try:
            staging.rename(destination)
        except OSError:
            if previous.exists() or previous.is_symlink():
                previous.rename(destination)
            raise


def install_neovim(work: Path, arch: str) -> None:
    archive = work / "nvim.tar.gz"
    download(release_asset("neovim/neovim", f"nvim-linux-{arch}.tar.gz"), archive)
    extract_tar(archive, work / "nvim")
    install_tree(work / "nvim" / f"nvim-linux-{arch}", OPT / "neovim")
    link_binary(OPT / "neovim/bin/nvim", "nvim")


def install_yazi(work: Path, arch: str) -> None:
    target = "aarch64" if arch == "arm64" else "x86_64"
    directory = f"yazi-{target}-unknown-linux-musl"
    archive = work / "yazi.zip"
    download(release_asset("sxyazi/yazi", f"{directory}.zip"), archive)
    with ZipFile(archive) as source:
        for name in ("yazi", "ya"):
            binary = work / name
            with (
                source.open(f"{directory}/{name}") as entry,
                binary.open("wb") as output,
            ):
                copyfileobj(entry, output)
            install_binary(binary, name)


def install_lazygit(work: Path, arch: str) -> None:
    release = read_json(
        "https://api.github.com/repos/jesseduffield/lazygit/releases/latest"
    )
    version = release["tag_name"].removeprefix("v")
    name = f"lazygit_{version}_linux_{arch}.tar.gz"
    matches = [
        asset
        for asset in release["assets"]
        if asset["name"].casefold() == name.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(f"Expected one release asset: {name}")
    archive = work / "lazygit.tar.gz"
    download(matches[0]["browser_download_url"], archive)
    extract_tar(archive, work / "lazygit")
    install_binary(work / "lazygit/lazygit", "lazygit")


def install_fzf(work: Path, arch: str) -> None:
    target = "amd64" if arch == "x86_64" else "arm64"
    release = read_json("https://api.github.com/repos/junegunn/fzf/releases/latest")
    version = release["tag_name"].removeprefix("v")
    name = f"fzf-{version}-linux_{target}.tar.gz"
    matches = [asset for asset in release["assets"] if asset["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Expected one release asset: {name}")
    archive = work / "fzf.tar.gz"
    download(matches[0]["browser_download_url"], archive)
    extract_tar(archive, work / "fzf")
    install_binary(work / "fzf/fzf", "fzf")


def install_node(work: Path, arch: str) -> None:
    releases = read_json("https://nodejs.org/dist/index.json")
    version = next((release["version"] for release in releases if release["lts"]), None)
    if version is None:
        raise ValueError("No Node.js LTS release found.")
    target = "x64" if arch == "x86_64" else "arm64"
    directory = f"node-{version}-linux-{target}"
    archive = work / "node.tar.xz"
    download(f"https://nodejs.org/dist/{version}/{directory}.tar.xz", archive)
    extract_tar(archive, work / "node")
    install_tree(work / "node" / directory, OPT / "node")
    for name in ("node", "npm", "npx"):
        link_binary(OPT / "node/bin" / name, name)


def validate_host() -> str:
    """Проверяет права, ОС и архитектуру до изменения системы."""
    if geteuid() != 0:
        raise ValueError("Run make system or make system-update as root.")
    if freedesktop_os_release().get("ID") != "ubuntu":
        raise ValueError("System installation supports Ubuntu only.")
    architectures = {"x86_64": "x86_64", "aarch64": "arm64", "arm64": "arm64"}
    arch = architectures.get(machine())
    if arch is None:
        raise ValueError("Supported architectures: x86_64, arm64.")
    return arch


def main(argv: list[str] | None = None) -> int:
    parser = ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        arch = validate_host()
        command("apt-get", "update")
        command("apt-get", "-o", "DPkg::Lock::Timeout=600", "install", "-y", *PACKAGES)
        BIN.mkdir(parents=True, exist_ok=True)
        OPT.mkdir(parents=True, exist_ok=True)
        link_binary(Path("/usr/bin/batcat"), "bat")
        link_binary(Path("/usr/bin/fdfind"), "fd")
        with TemporaryDirectory(prefix="server-dotfiles-") as temporary:
            work = Path(temporary)
            install_neovim(work, arch)
            install_yazi(work, arch)
            install_lazygit(work, arch)
            install_fzf(work, arch)
            install_node(work, arch)
    except (
        OSError,
        ValueError,
        KeyError,
        CalledProcessError,
        TarError,
        BadZipFile,
    ) as error:
        print(f"Installation failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
