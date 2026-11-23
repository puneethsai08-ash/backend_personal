# RoboBench Component Library

A Python-based component management and wiring validation module for RoboBench.

## Overview

The Component Library provides a structured system to define, validate, register and manage robotic hardware components.

It supports:
- YAML-based component definitions.
- JSON Schema structural validation.
- Semantic validation of component properties.
- Component registry and category filtering.
- Logical pin compatibility checking.
- Wiring connection management.
- JSON wiring configuration export.
- REST API integration through FastAPI.
- STL asset ingestion, physical metadata, and MJCF export.
- Hardware-CAD binding validation and simulation-bundle compilation.

## Technology Stack

- Python 3.12
- PyYAML
- JSON Schema
- jsonschema
- FastAPI
- Uvicorn
- Pydantic
- Pytest

## Project Structure

```text
robobench-backend/
├── components/
│   ├── microcontrollers/
│   │   └── stm32.yaml
│   ├── sensors/
│   │   ├── ldr.yaml
│   │   └── ultrasonic.yaml
│   └── actuators/
│       ├── servo.yaml
│       └── dc_motor_driver.yaml
│
├── schemas/
│   └── component.schema.json
│
├── src/
│   ├── validator.py
│   ├── registry.py
│   ├── wiring.py
│   ├── connection_manager.py
│   ├── cad.py
│   ├── binding.py
│   └── api.py
│
├── tests/
│   ├── fixtures/
│   ├── test_components.py
│   ├── test_wiring.py
│   ├── test_connection_manager.py
│   └── test_api.py
│
├── output/
│   └── wiring_config.json
│
├── requirements.txt
└── README.md

See [docs/cad_binding_guide.md](docs/cad_binding_guide.md) for CAD asset and
hardware-binding API details.
