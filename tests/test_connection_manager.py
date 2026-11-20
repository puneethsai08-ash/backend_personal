import json
from pathlib import Path

import pytest

from src.registry import ComponentRegistry
from src.connection_manager import (
    ConnectionManager,
    ConnectionManagerError,
)


BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def manager():
    registry = ComponentRegistry()
    registry.load_all()
    return ConnectionManager(registry)


def test_add_valid_connection(manager):
    connection = manager.add_connection(
        "SENSOR_ULTRASONIC_GENERIC",
        "ECHO",
        "MCU_STM32F407",
        "PA0",
    )

    assert connection["source"]["pin_id"] == "ECHO"
    assert manager.count() == 1


def test_invalid_connection_is_rejected(manager):
    with pytest.raises(ConnectionManagerError):
        manager.add_connection(
            "MCU_STM32F407",
            "PA0",
            "ACTUATOR_SERVO_GENERIC",
            "SIGNAL",
        )

    assert manager.count() == 0


def test_duplicate_connection_is_rejected(manager):
    arguments = (
        "SENSOR_ULTRASONIC_GENERIC",
        "ECHO",
        "MCU_STM32F407",
        "PA0",
    )

    manager.add_connection(*arguments)

    with pytest.raises(ConnectionManagerError):
        manager.add_connection(*arguments)

    assert manager.count() == 1


def test_remove_connection(manager):
    arguments = (
        "SENSOR_ULTRASONIC_GENERIC",
        "ECHO",
        "MCU_STM32F407",
        "PA0",
    )

    manager.add_connection(*arguments)

    assert manager.remove_connection(*arguments) is True
    assert manager.count() == 0


def test_export_json(manager, tmp_path):
    manager.add_connection(
        "MCU_STM32F407",
        "PB0",
        "ACTUATOR_SERVO_GENERIC",
        "SIGNAL",
    )

    output_file = tmp_path / "wiring.json"
    manager.save_json(output_file)

    assert output_file.exists()

    with output_file.open("r", encoding="utf-8") as file:
        data = json.load(file)

    assert data["schema_version"] == "1.0"
    assert len(data["connections"]) == 1
    assert (
        data["connections"][0]["source"]["component_id"]
        == "MCU_STM32F407"
    )
