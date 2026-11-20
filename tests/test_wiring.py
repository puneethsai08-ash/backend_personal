from pathlib import Path

import pytest

from src.validator import load_component
from src.wiring import (
    can_connect,
    validate_connection,
    WiringValidationError,
)


BASE_DIR = Path(__file__).resolve().parent.parent


def load_profile(relative_path):
    data = load_component(BASE_DIR / relative_path)
    return data["component"]


def test_sensor_output_to_mcu_input():
    sensor = load_profile("components/sensors/ultrasonic.yaml")
    mcu = load_profile("components/microcontrollers/stm32.yaml")

    assert can_connect(sensor, "ECHO", mcu, "PA0")


def test_mcu_output_to_servo_input():
    mcu = load_profile("components/microcontrollers/stm32.yaml")
    servo = load_profile("components/actuators/servo.yaml")

    assert can_connect(mcu, "PB0", servo, "SIGNAL")


def test_input_to_input_connection_rejected():
    mcu = load_profile("components/microcontrollers/stm32.yaml")
    servo = load_profile("components/actuators/servo.yaml")

    assert not can_connect(mcu, "PA0", servo, "SIGNAL")


def test_output_to_output_connection_rejected():
    mcu = load_profile("components/microcontrollers/stm32.yaml")
    sensor = load_profile("components/sensors/ultrasonic.yaml")

    assert not can_connect(sensor, "ECHO", mcu, "PB0")


def test_incompatible_pin_types_rejected():
    sensor = load_profile("components/sensors/ldr.yaml")
    servo = load_profile("components/actuators/servo.yaml")

    errors = validate_connection(
        sensor, "AO", servo, "VCC"
    )

    assert errors


def test_unknown_pin_raises_error():
    mcu = load_profile("components/microcontrollers/stm32.yaml")
    servo = load_profile("components/actuators/servo.yaml")

    with pytest.raises(WiringValidationError):
        validate_connection(
            mcu, "PA9", servo, "SIGNAL"
        )
