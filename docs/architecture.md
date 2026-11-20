# RoboBench Component Library — Architecture

## 1. Purpose

The Component Library provides a common system for defining, validating, registering and connecting hardware component profiles.

## 2. Architecture Overview

COMPONENT YAML FILES
        |
        v
YAML LOADER
        |
        v
JSON SCHEMA VALIDATOR
        |
        v
SEMANTIC VALIDATOR
        |
        v
COMPONENT REGISTRY
        |
        +------> COMPONENT API
        |
        v
WIRING COMPATIBILITY ENGINE
        |
        v
CONNECTION MANAGER
        |
        v
JSON EXPORT

## 3. Main Modules

### Component Definitions
Location: components/

Stores YAML profiles for microcontrollers, sensors and actuators.

### Component Schema
Location: schemas/component.schema.json

Defines the common structural format for component profiles.

### Validator
Location: src/validator.py

Loads YAML files and performs structural and semantic validation.

### Component Registry
Location: src/registry.py

Loads valid components, registers unique IDs and supports category filtering.

### Wiring Engine
Location: src/wiring.py

Checks logical pin compatibility and rejects invalid connections.

### Connection Manager
Location: src/connection_manager.py

Creates, removes, retrieves and exports wiring connections.

### REST API
Location: src/api.py

Exposes component and wiring operations through FastAPI.

## 4. Component Inventory

| Component ID | Category |
|---|---|
| MCU_STM32F407 | microcontroller |
| SENSOR_ULTRASONIC_GENERIC | sensor |
| SENSOR_LDR_GENERIC | sensor |
| ACTUATOR_SERVO_GENERIC | actuator |
| ACTUATOR_DC_MOTOR_DRIVER_GENERIC | actuator |

## 5. STM32F407 Logical Pin Mapping

| Pin | Role |
|---|---|
| PA0 | Digital input |
| PA1 | Digital input |
| PB0 | Digital output |
| PB1 | Digital output |

Physical package pin numbers are not yet established.

## 6. Validation Boundaries

Current validation covers component structure, selected electrical range consistency and logical pin compatibility.

Physical electrical safety, complete voltage/current compatibility and package-level pin mapping are not yet verified.

## 7. Runtime Behaviour

The API loads the component registry during initialization.

Connections are currently stored in application memory and are not persistent across server restarts.

## 8. Testing

The project currently has 23 passing automated tests covering component validation, wiring, connection management and API endpoints.

## 9. Current Limitations

- No database persistence.
- No complete electrical compatibility engine.
- No physical package pin verification.
- No Renode integration.
- No automatic integration with the main RoboBench backend.

Main backend integration and hardware-level verification remain pending.
