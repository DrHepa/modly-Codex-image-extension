from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_setup_module():
    setup_path = Path(__file__).resolve().parents[2] / "setup.py"
    spec = importlib.util.spec_from_file_location("modly_codex_setup", setup_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_args_accepts_modly_json_payload(tmp_path):
    module = _load_setup_module()

    payload = module.parse_args([
        '{"python_exe":"python3.12","ext_dir":"%s"}' % tmp_path,
    ])

    assert payload["python_exe"] == "python3.12"
    assert payload["ext_dir"] == str(tmp_path.resolve())
    assert "openai_codex_spec" not in payload


def test_parse_args_accepts_optional_official_sdk_spec(tmp_path):
    module = _load_setup_module()

    payload = module.parse_args([
        '{"python_exe":"python3.12","ext_dir":"%s","openai_codex_spec":"openai-codex==0.154.0"}' % tmp_path,
    ])

    assert payload["openai_codex_spec"] == "openai-codex==0.154.0"


def test_parse_args_rejects_sdk_cli_version_drift(tmp_path):
    module = _load_setup_module()

    try:
        module.parse_args([
            '{"python_exe":"python3.12","ext_dir":"%s","openai_codex_spec":"openai-codex==0.155.0"}' % tmp_path,
        ])
    except SystemExit as exc:
        assert "must match the reviewed pin" in str(exc)
    else:
        raise AssertionError("Expected setup to reject a drifting SDK override")


def test_resolve_openai_codex_spec_defaults_to_official_release_pin(tmp_path):
    module = _load_setup_module()

    payload = module.parse_args([
        '{"python_exe":"python3.12","ext_dir":"%s"}' % tmp_path,
    ])

    assert module.resolve_openai_codex_spec(payload) == "openai-codex==0.154.0"


def test_venv_python_executable_uses_windows_virtualenv_scripts_path(monkeypatch):
    module = _load_setup_module()
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    assert module.venv_python_executable(Path("venv")) == Path("venv") / "Scripts" / "python.exe"


def test_pip_install_invokes_python_module_to_allow_pip_self_upgrade(monkeypatch):
    module = _load_setup_module()
    calls: list[list[str]] = []

    monkeypatch.setattr(module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(module.subprocess, "run", lambda command, check: calls.append(list(command)))

    module.pip_install(Path("venv"), "install", "--upgrade", "pip", "setuptools", "wheel")

    assert calls == [[
        str(Path("venv") / "Scripts" / "python.exe"),
        "-m",
        "pip",
        "install",
        "--upgrade",
        "pip",
        "setuptools",
        "wheel",
    ]]


def test_normalize_payload_rejects_missing_python_exe(tmp_path):
    module = _load_setup_module()

    try:
        module.normalize_payload({"ext_dir": str(tmp_path)})
    except SystemExit as exc:
        assert "python_exe" in str(exc)
    else:
        raise AssertionError("Expected normalize_payload to reject missing python_exe")


def test_setup_extension_calls_bootstrap_steps_in_order(tmp_path, monkeypatch):
    module = _load_setup_module()
    calls: list[tuple[str, object]] = []

    def fake_create_venv(python_exe, ext_dir):
        calls.append(("create_venv", (python_exe, Path(ext_dir))))
        return tmp_path / "venv"

    def fake_bootstrap(venv_dir):
        calls.append(("bootstrap", Path(venv_dir)))

    def fake_install_sdk(venv_dir, payload):
        calls.append(("install_sdk", (Path(venv_dir), dict(payload))))

    def fake_verify_sdk(venv_dir):
        calls.append(("verify_sdk", Path(venv_dir)))

    monkeypatch.setattr(module, "create_venv", fake_create_venv)
    monkeypatch.setattr(module, "bootstrap_packaging_tools", fake_bootstrap)
    monkeypatch.setattr(module, "install_openai_codex", fake_install_sdk)
    monkeypatch.setattr(module, "verify_openai_codex", fake_verify_sdk)

    payload = {
        "python_exe": "python3.12",
        "ext_dir": str(tmp_path),
        "openai_codex_spec": "openai-codex==0.154.0",
    }

    module.setup_extension(payload)

    assert [entry[0] for entry in calls] == [
        "create_venv",
        "bootstrap",
        "install_sdk",
        "verify_sdk",
    ]
