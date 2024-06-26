"""Platform for light integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    API_CIRCUIT_SETSTATE,
    API_CIRCUIT_SETTHEME,
    API_LIGHTGROUP_SETSTATE,
    DESC,
    DOMAIN,
    EVENT_AVAILABILITY,
    EVENT_CIRCUIT,
    EVENT_LIGHTGROUP,
    PoolEquipmentClass,
)
from .entity import PoolEquipmentEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    config = coordinator.api.get_config()
    new_devices = []
    for circuit in config["circuits"]:
        try:
            if circuit["type"]["isLight"]:
                _lightthemes = {}
                for theme in await coordinator.api.get_lightthemes(circuit["id"]):
                    _lightthemes[theme["val"]] = theme[DESC]
                new_devices.append(
                    CircuitLight(
                        coordinator=coordinator,
                        equipment_class=PoolEquipmentClass.LIGHT,
                        circuit=circuit,
                        lightthemes=_lightthemes,
                    )
                )
        except KeyError:
            pass
    for group in config["lightGroups"]:
        _lightthemes = {}
        for theme in await coordinator.api.get_lightthemes(group["id"]):
            _lightthemes[theme["val"]] = theme[DESC]
        new_devices.append(
            CircuitLight(
                coordinator=coordinator,
                equipment_class=PoolEquipmentClass.LIGHT_GROUP,
                circuit=group,
                lightthemes=_lightthemes,
            )
        )

    if new_devices:
        async_add_entities(new_devices)


class CircuitLight(PoolEquipmentEntity, LightEntity):
    """Light entity for njsPC-HA."""

    def __init__(
        self,
        coordinator,
        equipment_class: PoolEquipmentClass,
        circuit: Any,
        lightthemes: Any,
    ) -> None:
        """Initialize the light."""
        match equipment_class:
            case PoolEquipmentClass.LIGHT:
                super().__init__(
                    coordinator=coordinator,
                    equipment_class=PoolEquipmentClass.LIGHT,
                    data=circuit,
                )
                self._event = EVENT_CIRCUIT
                self._command = API_CIRCUIT_SETSTATE
            case PoolEquipmentClass.LIGHT_GROUP:
                super().__init__(
                    coordinator=coordinator,
                    equipment_class=PoolEquipmentClass.LIGHT_GROUP,
                    data=circuit,
                )
                self._event = EVENT_LIGHTGROUP
                self._command = API_LIGHTGROUP_SETSTATE
        self._lightthemes = lightthemes
        self._value = None
        self._available = True
        if "isOn" in circuit:
            self._value = circuit["isOn"]
        self._lighting_theme = None
        self._attr_has_entity_name = False
        if "lightingTheme" in circuit:
            self._lighting_theme = circuit["lightingTheme"]["val"]

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (
            self.coordinator.data["event"] == self._event
            and self.coordinator.data["id"] == self.equipment_id
        ):
            if "isOn" in self.coordinator.data:
                self._value = self.coordinator.data["isOn"]
            if "lightingTheme" in self.coordinator.data:
                self._lighting_theme = self.coordinator.data["lightingTheme"]["val"]

            self.async_write_ha_state()
        elif self.coordinator.data["event"] == EVENT_AVAILABILITY:
            self._available = self.coordinator.data["available"]
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if ATTR_EFFECT in kwargs:
            if len(self._lightthemes) > 0:
                njspc_value = next(
                    (
                        k
                        for k, v in self._lightthemes.items()
                        if v == kwargs[ATTR_EFFECT]
                    ),
                    None,
                )
                if njspc_value is None:
                    self.coordinator.logger.error(
                        "Invalid theme for colorlogic light: %s", kwargs[ATTR_EFFECT]
                    )
                    return
                data = {"id": self.equipment_id, "theme": njspc_value}
                await self.coordinator.api.command(url=API_CIRCUIT_SETTHEME, data=data)
                return

        data = {"id": self.equipment_id, "state": True}
        await self.coordinator.api.command(url=self._command, data=data)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        data = {"id": self.equipment_id, "state": False}
        await self.coordinator.api.command(url=self._command, data=data)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def name(self) -> str:
        return self.equipment_name

    @property
    def unique_id(self) -> str:
        """Set unique device_id"""
        return f"{self.coordinator.controller_id}_{self.equipment_class}_{self.equipment_id}"

    @property
    def is_on(self) -> bool:
        try:
            return self._value
        except KeyError:
            return False

    @property
    def effect(self) -> str:
        """Which effect is active"""
        # Try not to load the stack with try catch for keyerror
        # don't know how efficeint the exception handling is
        if self._lighting_theme in self._lightthemes:
            return self._lightthemes[self._lighting_theme]
        return None

    @property
    def effect_list(self) -> list[str]:
        """Get list of effects."""
        if len(self._lightthemes) > 0:
            _effects = []
            for effect in self._lightthemes.values():
                _effects.append(effect)
            return _effects
        return None

    @property
    def supported_features(self) -> LightEntityFeature:
        """See if light has effects."""
        if len(self._lightthemes) > 0:
            return LightEntityFeature.EFFECT
        return LightEntityFeature(0)

    @property
    def color_mode(self) -> ColorMode:
        """Get color mode, always ONOFF for njs-PC."""
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Color mode list, only ONOFF for njs-PC."""
        return {ColorMode.ONOFF}
