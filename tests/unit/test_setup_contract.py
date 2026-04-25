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
    assert "codex_app_server_source" not in payload


def test_parse_args_accepts_optional_codex_source(tmp_path):
    module = _load_setup_module()

    payload = module.parse_args([
        '{"python_exe":"python3.12","ext_dir":"%s","codex_app_server_source":"git+https://example.invalid/codex.git"}' % tmp_path,
    ])

    assert payload["codex_app_server_source"] == "git+https://example.invalid/codex.git"


def test_resolve_codex_app_server_source_defaults_to_reviewed_pin(tmp_path):
    module = _load_setup_module()

    payload = module.parse_args([
        '{"python_exe":"python3.12","ext_dir":"%s"}' % tmp_path,
    ])

    assert module.resolve_codex_app_server_source(payload) == module.DEFAULT_CODEX_APP_SERVER_SOURCE


def test_pip_executable_uses_windows_virtualenv_scripts_path(monkeypatch):
    module = _load_setup_module()
    monkeypatch.setattr(module.platform, "system", lambda: "Windows")

    assert module.pip_executable(Path("venv")) == Path("venv") / "Scripts" / "pip.exe"


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

    def fake_install_optional(venv_dir, payload):
        calls.append(("install_optional", (Path(venv_dir), dict(payload))))

    monkeypatch.setattr(module, "create_venv", fake_create_venv)
    monkeypatch.setattr(module, "bootstrap_packaging_tools", fake_bootstrap)
    monkeypatch.setattr(module, "install_optional_codex_app_server", fake_install_optional)

    payload = {
        "python_exe": "python3.12",
        "ext_dir": str(tmp_path),
        "codex_app_server_source": "git+https://example.invalid/codex.git",
    }

    module.setup_extension(payload)

    assert [entry[0] for entry in calls] == [
        "create_venv",
        "bootstrap",
        "install_optional",
    ]
