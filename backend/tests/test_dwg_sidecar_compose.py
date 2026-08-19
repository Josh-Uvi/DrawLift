"""Tests for the GNU LibreDWG sidecar Docker wiring (US-032)."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
DOCKERFILE_PATH = REPO_ROOT / "backend" / "Dockerfile.libredwg"
ENTRYPOINT_PATH = REPO_ROOT / "backend" / "libredwg-entrypoint.sh"


def _compose() -> dict[str, object]:
    data = yaml.safe_load(COMPOSE_PATH.read_text())
    assert isinstance(data, dict)
    return data


def _service(name: str) -> dict[str, object]:
    services = _compose()["services"]
    assert isinstance(services, dict)
    service = services[name]
    assert isinstance(service, dict)
    return service


def test_libredwg_dockerfile_exists() -> None:
    """T-104: the repository contains a dedicated LibreDWG Dockerfile."""
    assert DOCKERFILE_PATH.is_file()
    assert ENTRYPOINT_PATH.is_file()


def test_libredwg_dockerfile_builds_from_gnu_source() -> None:
    """T-104: the Dockerfile downloads GNU LibreDWG and installs dwgwrite."""
    content = DOCKERFILE_PATH.read_text()

    assert "ftp.gnu.org/gnu/libredwg" in content
    configure_line = (
        './configure --prefix="${LIBREDWG_DIST}" ' "--disable-bindings --disable-python"
    )
    assert configure_line in content
    assert "make install" in content
    assert "dwgwrite-real" in content
    assert 'ENTRYPOINT ["/usr/local/bin/libredwg-entrypoint.sh"]' in content


def test_dwg_converter_profile_uses_libredwg_image() -> None:
    """AC: the placeholder alpine profile is replaced by the GNU LibreDWG build."""
    service = _service("dwg-converter")

    build = service.get("build")
    assert isinstance(build, dict)
    assert build.get("context") == "./backend"
    assert build.get("dockerfile") == "Dockerfile.libredwg"
    assert service.get("profiles") == ["dwg"]


def test_backend_worker_and_beat_auto_configure_dwgwrite_command() -> None:
    """T-106: compose auto-configures DWG_CONVERTER_COMMAND for runtime services."""
    expected = "${DWG_CONVERTER_COMMAND:-dwgwrite {input} {output}}"
    expected_path = "/opt/libredwg/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    for service_name in ("backend", "worker", "beat"):
        environment = _service(service_name)["environment"]
        assert isinstance(environment, dict)
        assert environment.get("DWG_CONVERTER_COMMAND") == expected
        assert environment.get("PATH") == expected_path
        assert environment.get("LD_LIBRARY_PATH") == "/opt/libredwg/lib"


def test_runtime_services_mount_the_shared_libredwg_volume() -> None:
    """The sidecar populates a shared /opt/libredwg tree for other services."""
    for service_name in ("backend", "worker", "beat"):
        volumes = _service(service_name)["volumes"]
        assert isinstance(volumes, list)
        assert "libredwg_root:/opt/libredwg:ro" in volumes

    sidecar_volumes = _service("dwg-converter")["volumes"]
    assert isinstance(sidecar_volumes, list)
    assert "libredwg_root:/opt/libredwg" in sidecar_volumes


def test_compose_declares_named_libredwg_volume() -> None:
    volumes = _compose()["volumes"]
    assert isinstance(volumes, dict)
    assert "libredwg_root" in volumes
