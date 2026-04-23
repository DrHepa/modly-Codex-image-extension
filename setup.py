#!/usr/bin/env python3
"""Bootstrap script for the Modly Codex image extension.

This script follows Modly's current Python-root setup contract:

    python setup.py '<json-payload>'

Where the payload JSON may include at least:
    python_exe  -- path to the Python executable Modly wants us to use
    ext_dir     -- absolute path to the extension directory

Optional payload keys accepted by this extension:
    codex_app_server_source -- reviewed source/install reference for codex_app_server

The script intentionally avoids setuptools/distutils command parsing because Modly
passes the payload as a single JSON positional argument.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_CODEX_APP_SERVER_SOURCE = (
    "git+https://github.com/openai/codex.git"
    "@a9f75e5cda2d6ff469a859baf8d2f50b9b04944a"
    "#subdirectory=sdk/python"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def pip_executable(venv_dir: Path) -> Path:
    if platform.system() == "Windows":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    argv = list(sys.argv[1:] if argv is None else argv)

    if len(argv) >= 2:
        payload = {
            "python_exe": argv[0],
            "ext_dir": argv[1],
        }
        if len(argv) >= 3:
            payload["codex_app_server_source"] = argv[2]
        return normalize_payload(payload)

    if len(argv) == 1:
        try:
            raw_payload = json.loads(argv[0])
        except json.JSONDecodeError as exc:
            raise SystemExit(f"setup payload must be valid JSON: {exc}") from exc
        if not isinstance(raw_payload, dict):
            raise SystemExit("setup payload must be a JSON object")
        return normalize_payload(raw_payload)

    raise SystemExit(
        "Usage: python setup.py '<json-payload>'\n"
        "   or: python setup.py <python_exe> <ext_dir> [codex_app_server_source]"
    )


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    python_exe = payload.get("python_exe")
    ext_dir = payload.get("ext_dir")
    codex_source = payload.get("codex_app_server_source")

    if not isinstance(python_exe, str) or not python_exe.strip():
        raise SystemExit("setup payload must include a non-empty python_exe")

    if not isinstance(ext_dir, str) or not ext_dir.strip():
        raise SystemExit("setup payload must include a non-empty ext_dir")

    normalized = {
        "python_exe": python_exe.strip(),
        "ext_dir": str(Path(ext_dir.strip()).expanduser().resolve()),
    }

    if isinstance(codex_source, str) and codex_source.strip():
        normalized["codex_app_server_source"] = codex_source.strip()

    return normalized


def resolve_codex_app_server_source(payload: dict[str, Any]) -> str:
    source = payload.get("codex_app_server_source")
    if isinstance(source, str) and source.strip():
        return source.strip()

    env_source = os.environ.get("CODEX_APP_SERVER_SOURCE")
    if isinstance(env_source, str) and env_source.strip():
        return env_source.strip()

    return DEFAULT_CODEX_APP_SERVER_SOURCE


def create_venv(python_exe: str, ext_dir: Path) -> Path:
    venv_dir = ext_dir / "venv"
    print(f"[setup] Creating extension venv at {venv_dir} …")
    subprocess.run([python_exe, "-m", "venv", str(venv_dir)], check=True)
    return venv_dir


def pip_install(venv_dir: Path, *args: str) -> None:
    pip_exe = pip_executable(venv_dir)
    subprocess.run([str(pip_exe), *args], check=True)


def bootstrap_packaging_tools(venv_dir: Path) -> None:
    print("[setup] Bootstrapping pip/setuptools/wheel in extension venv …")
    pip_install(venv_dir, "install", "--upgrade", "pip", "setuptools", "wheel")


def install_optional_codex_app_server(venv_dir: Path, payload: dict[str, Any]) -> None:
    source = resolve_codex_app_server_source(payload)

    print(f"[setup] Installing codex_app_server from reviewed source: {source}")
    pip_install(venv_dir, "install", source)


def setup_extension(payload: dict[str, Any]) -> None:
    ext_dir = Path(payload["ext_dir"])
    venv_dir = create_venv(payload["python_exe"], ext_dir)
    bootstrap_packaging_tools(venv_dir)
    install_optional_codex_app_server(venv_dir, payload)
    print(f"[setup] Done. Extension venv ready at: {venv_dir}")


def main(argv: list[str] | None = None) -> int:
    payload = parse_args(argv)
    setup_extension(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
