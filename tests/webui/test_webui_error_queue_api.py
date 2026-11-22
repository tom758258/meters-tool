from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from meters_tool_core.runner import StartRunnerDependencies
from meters_tool_core.simulator import SimulatedVisaInstrument
from webui_test_helpers import wait_until_inactive

try:
    from fastapi.testclient import TestClient
    from meters_tool_webui import _run_manager
    from meters_tool_webui.web_ui import WebRunManager, create_app
except ModuleNotFoundError:
    pytest.skip("FastAPI test dependencies are not installed", allow_module_level=True)


DIAGNOSTIC = "/api/diagnostics/error-queue"
RUN = {
    "resource": "SIM::34461A",
    "instrument_model": "34461A",
    "simulate": True,
    "trigger_mode": "software",
    "max_samples": 1,
    "csv_enabled": False,
}


@pytest.mark.parametrize("invalid", [{"max_reads": 0}, {"max_reads": True}, {"max_reads": 1.5}, {"simulate": True}])
def test_invalid_diagnostic_payload_never_opens_visa(monkeypatch, invalid):
    factory = Mock(side_effect=AssertionError("unexpected VISA I/O"))
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    client = TestClient(create_app())
    assert client.post(DIAGNOSTIC, json={"resource": "USB::FAKE::INSTR", **invalid}).status_code == 422
    factory.assert_not_called()


@pytest.mark.parametrize(("mode", "reads"), [("simulate", 1), ("dry-run", 0)])
def test_diagnostic_no_hardware_modes_leave_run_status_unchanged(monkeypatch, mode, reads):
    factory = Mock(side_effect=AssertionError("unexpected VISA I/O"))
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    client = TestClient(create_app())
    status = client.get("/api/runs/current").json()
    response = client.post(DIAGNOSTIC, json={"mode": mode, "instrument_model": "34460A"})
    assert response.status_code == 200
    assert response.json()["reads"] == reads
    assert response.json()["max_reads"] == 20
    assert client.get("/api/runs/current").json() == status
    factory.assert_not_called()


def test_diagnostic_blocks_measurement_through_close_and_releases_after_failure(monkeypatch):
    closing = Event()
    release = Event()
    factory = Mock()
    instrument = factory.return_value.open_resource.return_value
    instrument.query.side_effect = ["Keysight Technologies,34461A,FAKE,1.0", TimeoutError()]

    def close():
        closing.set()
        assert release.wait(5)

    instrument.close.side_effect = close
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    client = TestClient(create_app())
    with ThreadPoolExecutor() as executor:
        diagnostic = executor.submit(client.post, DIAGNOSTIC, json={
            "resource": "TCPIP::meter.example::INSTR",
            "visa_library": "@py",
            "max_reads": 3,
        })
        try:
            assert closing.wait(5)
            assert client.post("/api/runs", json=RUN).status_code == 409
            assert client.post(DIAGNOSTIC, json={"mode": "simulate", "instrument_model": "34461A"}).status_code == 409
        finally:
            release.set()
        assert diagnostic.result(timeout=5).status_code == 503

    factory.assert_called_once_with("@py")
    assert client.post("/api/runs", json=RUN).status_code == 200
    client.post("/api/runs/current/stop")
    assert not wait_until_inactive(client)["active"]


@pytest.mark.parametrize("first_operation", ["scan", "diagnostic"])
def test_live_diagnostic_and_resource_scan_do_not_overlap(monkeypatch, first_operation):
    resource = "TCPIP::meter.example::INSTR"
    idn = "Keysight Technologies,34461A,FAKE,1.0"
    scan_path = "/api/resources?verify=true&live_only=true&visa_library=%40py"
    entered = Event()
    release = Event()

    def hold_session():
        entered.set()
        assert release.wait(5)

    enumerate_resources = Mock(return_value=[resource])
    verify = Mock(return_value=(True, idn))
    factory = Mock()
    manager = factory.return_value
    instrument = manager.open_resource.return_value
    instrument.query.side_effect = [idn, '0,"No error"']

    if first_operation == "scan":
        def verify_resource(*args, **kwargs):
            hold_session()
            return True, idn

        verify.side_effect = verify_resource
    else:
        manager.close.side_effect = hold_session

    monkeypatch.setattr(_run_manager.VisaInstrument, "list_resources", enumerate_resources)
    monkeypatch.setattr(_run_manager.VisaInstrument, "verify_resource", verify)
    monkeypatch.setattr("meters_tool_core.diagnostics._create_resource_manager", factory)
    client = TestClient(create_app())

    def scan():
        return client.get(scan_path)

    def diagnose():
        return client.post(DIAGNOSTIC, json={"resource": resource, "visa_library": "@py"})

    with ThreadPoolExecutor() as executor:
        first = executor.submit(scan if first_operation == "scan" else diagnose)
        try:
            assert entered.wait(5)
            if first_operation == "scan":
                assert diagnose().status_code == 409
                factory.assert_not_called()
            else:
                assert scan().status_code == 409
                enumerate_resources.assert_not_called()
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200

    second = diagnose if first_operation == "scan" else scan
    assert second().status_code == 200


def test_measurement_blocks_diagnostic_during_start_run_and_cleanup(monkeypatch):
    resolving = Event()
    allow_start = Event()
    cleaning_up = Event()
    allow_cleanup = Event()
    resolve = _run_manager.resolve_start_profile

    def resolve_profile(request):
        resolving.set()
        assert allow_start.wait(5)
        return resolve(request)

    class CleanupBarrier(SimulatedVisaInstrument):
        def cleanup_release_to_local(self, timeout_ms=1000):
            cleaning_up.set()
            assert allow_cleanup.wait(5)
            return super().cleanup_release_to_local(timeout_ms)

    def backend(config, **_options):
        return CleanupBarrier(config)

    monkeypatch.setattr(_run_manager, "resolve_start_profile", resolve_profile)
    manager = WebRunManager(runner_dependencies=StartRunnerDependencies(instrument_backend_factory=backend))
    client = TestClient(create_app(manager))
    payload = {"mode": "simulate", "instrument_model": "34461A"}

    with ThreadPoolExecutor() as executor:
        started = executor.submit(client.post, "/api/runs", json=RUN)
        try:
            assert resolving.wait(5)
            assert client.post(DIAGNOSTIC, json=payload).status_code == 409
            allow_start.set()
            assert started.result(timeout=5).status_code == 200
            assert client.post(DIAGNOSTIC, json=payload).status_code == 409
            assert client.post("/api/runs/current/stop").status_code == 202
            assert cleaning_up.wait(5)
            assert client.post(DIAGNOSTIC, json=payload).status_code == 409
            allow_cleanup.set()
            assert not wait_until_inactive(client)["active"]
            assert client.post(DIAGNOSTIC, json=payload).status_code == 200
        finally:
            allow_start.set()
            allow_cleanup.set()
            manager.shutdown()
