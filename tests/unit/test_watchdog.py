import subprocess
import pytest
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

spec = spec_from_file_location("host_watchdog", Path(__file__).parents[2] / "scripts" / "host-watchdog.py")
watchdog = module_from_spec(spec); spec.loader.exec_module(watchdog)

def test_host_stop_checks_allowlisted_service(monkeypatch):
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1] == "is-active": return subprocess.CompletedProcess(command, 3, "inactive", "")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    assert watchdog.stop_host_unit("cri-agents.service", "/fake/systemctl")
    assert len(calls) == 2

def test_host_stop_refuses_arbitrary_unit():
    with pytest.raises(ValueError): watchdog.stop_host_unit("ssh.service")

def test_host_stop_detects_service_still_active(monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, "activating", "")
    monkeypatch.setattr(watchdog.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="still active"):
        watchdog.stop_host_unit("cri-agents.service")
