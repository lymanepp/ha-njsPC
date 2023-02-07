"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant


from .controller import FreezeProtectionSensor
from .pumps import PumpOnSensor
from .bodies import FilterOnSensor

from .const import (
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for past config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    new_devices = []
    config = coordinator.api.get_config()

    new_devices.append(FreezeProtectionSensor(coordinator, config))
    # Add in a binary sensor for all pumps.
    for pump in config["pumps"]:
        new_devices.append(PumpOnSensor(coordinator=coordinator, pump=pump))

    for pool_filter in config["filters"]:
        new_devices.append(
            FilterOnSensor(coordinator=coordinator, pool_filter=pool_filter)
        )

    if new_devices:
        async_add_entities(new_devices)
