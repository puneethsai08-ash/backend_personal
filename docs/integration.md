# RoboBench Component Library — Integration Guide

## 1. Purpose

This guide explains how other RoboBench backend modules can access the Component Library.

The integration conventions described here are proposed interfaces and should be reviewed by the backend team before production integration.

## 2. Component Registry

Other Python modules can access components using:

```python
from src.registry import ComponentRegistry

registry = ComponentRegistry()
registry.load_all()

mcu = registry.get("MCU_STM32F407")
sensor = registry.get("SENSOR_ULTRASONIC_GENERIC")
servo = registry.get("ACTUATOR_SERVO_GENERIC")
