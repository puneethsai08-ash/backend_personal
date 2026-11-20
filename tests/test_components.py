import pytest
from pathlib import Path
from src.validator import validate_component


BASE_DIR = Path(__file__).resolve().parent.parent

VALID_FILE = (
    BASE_DIR / "components/microcontrollers/stm32.yaml"
)

INVALID_FILE = (
    BASE_DIR / "components/microcontrollers/invalid_stm32.yaml"
)


def test_valid_component():
    assert validate_component(VALID_FILE) is True


def test_invalid_component():
    assert validate_component(INVALID_FILE) is False