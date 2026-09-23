#!/usr/bin/env python3
"""Bootstrap script for the Modly Codex image extension.

This script follows Modly's current Python-root setup contract:

    python setup.py '<json-payload>'

Where the payload JSON may include at least:
    python_exe  -- path to the Python executable Modly wants us to use
    ext_dir     -- absolute path to the extension directory

Optional payload keys accepted by this extension:
    openai_codex_spec -- must match the pinned official SDK release

The script intentionally avoids setuptools/distutils command parsing because Modly
passes the payload as a single JSON positional argument.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_OPENAI_CODEX_SPEC = "openai-codex==0.154.0"


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def venv_python_executable(venv_dir: Path) -> Path:
    if platform.system() == "Windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    argv = list(sys.argv[1:] if argv is None else argv)

    if len(argv) >= 2:
        payload = {
            "python_exe": argv[0],
            "ext_dir": argv[1],
        }
        if len(argv) >= 3:
            payload["openai_codex_spec"] = argv[2]
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
        "   or: python setup.py <python_exe> <ext_dir> [openai_codex_spec]"
    )


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    python_exe = payload.get("python_exe")
    ext_dir = payload.get("ext_dir")
    codex_spec = payload.get("openai_codex_spec")

    if not isinstance(python_exe, str) or not python_exe.strip():
        raise SystemExit("setup payload must include a non-empty python_exe")

    if not isinstance(ext_dir, str) or not ext_dir.strip():
        raise SystemExit("setup payload must include a non-empty ext_dir")

    normalized = {
        "python_exe": python_exe.strip(),
        "ext_dir": str(Path(ext_dir.strip()).expanduser().resolve()),
    }

    if isinstance(codex_spec, str) and codex_spec.strip():
        normalized_spec = codex_spec.strip()
        if normalized_spec != DEFAULT_OPENAI_CODEX_SPEC:
            raise SystemExit(
                "openai_codex_spec must match the reviewed pin "
                f"{DEFAULT_OPENAI_CODEX_SPEC}"
            )
        normalized["openai_codex_spec"] = normalized_spec

    return normalized


def resolve_openai_codex_spec(payload: dict[str, Any]) -> str:
    spec = payload.get("openai_codex_spec")
    if isinstance(spec, str) and spec.strip():
        return spec.strip()
    return DEFAULT_OPENAI_CODEX_SPEC


def create_venv(python_exe: str, ext_dir: Path) -> Path:
    venv_dir = ext_dir / "venv"
    print(f"[setup] Creating extension venv at {venv_dir} …")
    subprocess.run([python_exe, "-m", "venv", str(venv_dir)], check=True)
    return venv_dir


def pip_install(venv_dir: Path, *args: str) -> None:
    python_exe = venv_python_executable(venv_dir)
    subprocess.run([str(python_exe), "-m", "pip", *args], check=True)


def bootstrap_packaging_tools(venv_dir: Path) -> None:
    print("[setup] Bootstrapping pip/setuptools/wheel in extension venv …")
    pip_install(venv_dir, "install", "--upgrade", "pip", "setuptools", "wheel")


def install_openai_codex(venv_dir: Path, payload: dict[str, Any]) -> None:
    spec = resolve_openai_codex_spec(payload)
    print(f"[setup] Installing official Codex Python SDK: {spec}")
    pip_install(venv_dir, "install", spec)


def verify_openai_codex(venv_dir: Path) -> None:
    print("[setup] Verifying the pinned official Codex SDK/runtime pair …")
    pip_install(venv_dir, "check")
    verification = (
        "from importlib.metadata import version; "
        "from openai_codex import Codex, LocalImageInput, Sandbox, TextInput; "
        "assert version('openai-codex') == '0.154.0'; "
        "assert version('openai-codex-cli-bin') == '0.154.0'; "
        "assert Codex and LocalImageInput and Sandbox and TextInput"
    )
    subprocess.run(
        [str(venv_python_executable(venv_dir)), "-c", verification],
        check=True,
    )


def setup_extension(payload: dict[str, Any]) -> None:
    ext_dir = Path(payload["ext_dir"])
    venv_dir = create_venv(payload["python_exe"], ext_dir)
    bootstrap_packaging_tools(venv_dir)
    install_openai_codex(venv_dir, payload)
    verify_openai_codex(venv_dir)
    print(f"[setup] Done. Extension venv ready at: {venv_dir}")


def main(argv: list[str] | None = None) -> int:
    payload = parse_args(argv)
    setup_extension(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
