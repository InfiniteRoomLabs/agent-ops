# /// script
# dependencies = ["typer>=0.15"]
# ///
"""Render a mermaid diagram and open it for the user.

Defaults are tuned for Linux + sandboxed browsers (snap Firefox, AppArmor):
- PDF output (vector, baked fonts, dark-mode-proof, viewer-portable)
- writes to ~/Downloads/ so snap/flatpak browsers can read it
- supplies --no-sandbox to Puppeteer/Chromium for Ubuntu 23.10+ AppArmor

Usage:
  uv run render_mermaid.py from-file <path.mmd> [--format pdf|svg|png] [--no-open]
  uv run render_mermaid.py from-stdin              [--format pdf|svg|png] [--no-open]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(
    help="Render a mermaid diagram to an image or PDF and open it.",
    no_args_is_help=True,
)

VALID_FORMATS = ("pdf", "svg", "png")
DEFAULT_FORMAT = "pdf"


def _output_dir() -> Path:
    """Pick a directory readable by snap/flatpak browsers.

    /tmp is invisible to snap Firefox; ~/Downloads is on the default snap
    permission list. Fall back to a temp dir only if Downloads is missing.
    """
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    return Path(tempfile.gettempdir())


def _puppeteer_config() -> Path:
    """Write a one-shot puppeteer config that disables Chromium's sandbox.

    Ubuntu 23.10+ AppArmor blocks unprivileged user namespaces so Puppeteer's
    bundled Chromium fails with FATAL: No usable sandbox.
    """
    cfg = Path(tempfile.gettempdir()) / "mermaid-puppeteer.json"
    cfg.write_text(json.dumps({"args": ["--no-sandbox"]}), encoding="utf-8")
    return cfg


def _render(src: Path, fmt: str) -> Path:
    if fmt not in VALID_FORMATS:
        typer.echo(f"format must be one of {VALID_FORMATS}", err=True)
        raise typer.Exit(2)

    out = _output_dir() / f"{src.stem}.{fmt}"
    cfg = _puppeteer_config()

    cmd = [
        "npx", "-y", "-p", "@mermaid-js/mermaid-cli",
        "mmdc",
        "-i", str(src),
        "-o", str(out),
        "-b", "white",
        "-t", "default",
        "-p", str(cfg),
    ]
    typer.echo(f"rendering {src.name} -> {out}", err=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        typer.echo(result.stderr, err=True)
        raise typer.Exit(result.returncode)
    return out


def _open_detached(path: Path) -> None:
    """xdg-open the file, fully detached so the agent's shell can return."""
    if not shutil.which("xdg-open"):
        typer.echo(f"rendered: {path} (no xdg-open available)", err=True)
        return
    subprocess.Popen(
        ["xdg-open", str(path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    typer.echo(f"opened: {path}", err=True)


@app.command("from-file")
def from_file(
    path: Annotated[Path, typer.Argument(help="Path to a .mmd / .mermaid file.")],
    fmt: Annotated[
        str, typer.Option("--format", "-f", help="pdf | svg | png")
    ] = DEFAULT_FORMAT,
    open_after: Annotated[
        bool, typer.Option("--open/--no-open", help="Open with xdg-open after render.")
    ] = True,
) -> None:
    """Render a mermaid file to an image or PDF and open it."""
    if not path.is_file():
        typer.echo(f"not a file: {path}", err=True)
        raise typer.Exit(1)
    out = _render(path, fmt)
    if open_after:
        _open_detached(out)
    print(out)


@app.command("from-stdin")
def from_stdin(
    name: Annotated[
        Optional[str],
        typer.Option("--name", "-n", help="Stem for the rendered file."),
    ] = "diagram",
    fmt: Annotated[
        str, typer.Option("--format", "-f", help="pdf | svg | png")
    ] = DEFAULT_FORMAT,
    open_after: Annotated[
        bool, typer.Option("--open/--no-open", help="Open with xdg-open after render.")
    ] = True,
) -> None:
    """Read mermaid source from stdin, render, and open."""
    src_text = sys.stdin.read()
    if not src_text.strip():
        typer.echo("stdin was empty -- pass mermaid source on stdin", err=True)
        raise typer.Exit(1)
    tmp = Path(tempfile.gettempdir()) / f"{name or 'diagram'}.mmd"
    tmp.write_text(src_text, encoding="utf-8")
    out = _render(tmp, fmt)
    if open_after:
        _open_detached(out)
    print(out)


if __name__ == "__main__":
    # Detach from the parent shell's stdout/stderr where we can so the
    # agent's tool call returns promptly even if the viewer lingers.
    os.environ.setdefault("MMDCLI_LOG_LEVEL", "error")
    app()
