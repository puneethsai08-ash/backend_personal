import pytest
from fastapi.testclient import TestClient

from src.api import app, connection_manager


@pytest.fixture
def client():
    connection_manager.connections.clear()

    with TestClient(app) as test_client:
        yield test_client

    connection_manager.connections.clear()


def test_home_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["version"] == "1.0.0"


def test_get_all_components(client):
    response = client.get("/components")

    assert response.status_code == 200
    assert response.json()["total"] == 5


def test_get_sensor_category(client):
    response = client.get("/components/category/sensor")

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_get_component_by_id(client):
    response = client.get("/components/MCU_STM32F407")

    assert response.status_code == 200
    assert response.json()["name"] == "STM32F407"


def test_unknown_component_returns_404(client):
    response = client.get("/components/UNKNOWN")

    assert response.status_code == 404


def test_validate_connection_api(client):
    response = client.post(
        "/connections/validate",
        json={
            "source_component_id": "SENSOR_ULTRASONIC_GENERIC",
            "source_pin_id": "ECHO",
            "target_component_id": "MCU_STM32F407",
            "target_pin_id": "PA0"
        }
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_create_connection_api(client):
    response = client.post(
        "/connections",
        json={
            "source_component_id": "MCU_STM32F407",
            "source_pin_id": "PB0",
            "target_component_id": "ACTUATOR_SERVO_GENERIC",
            "target_pin_id": "SIGNAL"
        }
    )

    assert response.status_code == 201
    assert response.json()["connection"]["source"]["pin_id"] == "PB0"


def test_duplicate_connection_api_rejected(client):
    payload = {
        "source_component_id": "MCU_STM32F407",
        "source_pin_id": "PB0",
        "target_component_id": "ACTUATOR_SERVO_GENERIC",
        "target_pin_id": "SIGNAL"
    }

    first = client.post("/connections", json=payload)
    second = client.post("/connections", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400


def test_get_connections_api(client):
    response = client.get("/connections")

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_export_connections_api(client):
    response = client.get("/connections/export")

    assert response.status_code == 200
    assert response.json()["schema_version"] == "1.0"
    assert response.json()["connections"] == []
