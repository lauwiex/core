"""Support for OVO Energy sensors."""
from datetime import datetime, timedelta
import logging

import aiohttp
import async_timeout
from ovoenergy import OVODailyElectricity, OVODailyGas, OVODailyUsage
from ovoenergy.ovoenergy import OVOEnergy

from homeassistant.components.ovo_energy import OVOEnergyDeviceEntity
from homeassistant.components.ovo_energy.const import (
    CONF_ACCOUNT_ID,
    DATA_OVO_ENERGY_CLIENT,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)
PARALLEL_UPDATES = 4


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up OVO Energy sensor based on a config entry."""
    instance_key = f"{DOMAIN}_{entry.data[CONF_ACCOUNT_ID]}"
    client = hass.data[instance_key][DATA_OVO_ENERGY_CLIENT]

    now = datetime.utcnow()
    try:
        usage: OVODailyUsage = await client.get_daily_usage(now.strftime("%Y-%m"))
        currency = usage.electricity[len(usage.electricity) - 1].cost.currency_unit
    except aiohttp.ClientError as exception:
        _LOGGER.warning(exception)
        raise PlatformNotReady from exception

    async def async_update_data() -> OVODailyUsage:
        """Fetch data from OVO Energy."""
        now = datetime.utcnow()
        async with async_timeout.timeout(10):
            return await client.get_daily_usage(now.strftime("%Y-%m"))

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="sensor",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=30),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    async_add_entities(
        [
            OVOEnergyLastElectricityReading(coordinator, client),
            OVOEnergyLastGasReading(coordinator, client),
            OVOEnergyLastElectricityCost(coordinator, client, currency),
            OVOEnergyLastGasCost(coordinator, client, currency),
        ],
        True,
    )


class OVOEnergySensor(OVOEnergyDeviceEntity):
    """Defines a OVO Energy sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        client: OVOEnergy,
        key: str,
        name: str,
        icon: str,
        unit_of_measurement: str = "",
    ) -> None:
        """Initialize OVO Energy sensor."""
        self._coordinator = coordinator
        self._state = None
        self._attributes = None
        self._available = False
        self._unit_of_measurement = unit_of_measurement

        super().__init__(client, key, name, icon)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return self._key

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self) -> object:
        """Return the attributes of the sensor."""
        return self._attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False


class OVOEnergyLastElectricityReading(OVOEnergySensor):
    """Defines a OVO Energy last reading sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: OVOEnergy):
        """Initialize OVO Energy sensor."""

        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_electricity_reading",
            "OVO Last Electricity Reading",
            "mdi:flash",
            "kWh",
        )

    async def _ovo_energy_update(self) -> bool:
        """Update OVO Energy entity."""
        await self._coordinator.async_request_refresh()
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or usage.electricity is None:
            _LOGGER.warning("No data found for %s", self._name)
            self._available = False
            return False
        last_reading: OVODailyElectricity = usage.electricity[
            len(usage.electricity) - 1
        ]
        self._state = last_reading.consumption
        self._attributes = {
            "start_time": last_reading.interval.start,
            "end_time": last_reading.interval.end,
        }
        self._available = True
        return True


class OVOEnergyLastGasReading(OVOEnergySensor):
    """Defines a OVO Energy last reading sensor."""

    def __init__(self, coordinator: DataUpdateCoordinator, client: OVOEnergy):
        """Initialize OVO Energy sensor."""

        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_reading",
            "OVO Last Gas Reading",
            "mdi:gas-cylinder",
            "kWh",
        )

    async def _ovo_energy_update(self) -> bool:
        """Update OVO Energy entity."""
        await self._coordinator.async_request_refresh()
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or usage.gas is None:
            _LOGGER.warning("No data found for %s", self._name)
            self._available = False
            return False
        last_reading: OVODailyGas = usage.gas[len(usage.gas) - 1]
        self._state = last_reading.consumption
        self._attributes = {
            "start_time": last_reading.interval.start,
            "end_time": last_reading.interval.end,
        }
        self._available = True
        return True


class OVOEnergyLastElectricityCost(OVOEnergySensor):
    """Defines a OVO Energy last cost sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, client: OVOEnergy, currency: str
    ):
        """Initialize OVO Energy sensor."""
        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_electricity_cost",
            "OVO Last Electricity Cost",
            "mdi:cash-multiple",
            currency,
        )

    async def _ovo_energy_update(self) -> bool:
        """Update OVO Energy entity."""
        await self._coordinator.async_request_refresh()
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or usage.electricity is None:
            _LOGGER.warning("No data found for %s", self._name)
            self._available = False
            return False
        last_reading: OVODailyElectricity = usage.electricity[
            len(usage.electricity) - 1
        ]
        self._state = last_reading.cost.amount
        self._attributes = {
            "start_time": last_reading.interval.start,
            "end_time": last_reading.interval.end,
        }
        self._available = True
        return True


class OVOEnergyLastGasCost(OVOEnergySensor):
    """Defines a OVO Energy last cost sensor."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, client: OVOEnergy, currency: str
    ):
        """Initialize OVO Energy sensor."""
        super().__init__(
            coordinator,
            client,
            f"{DOMAIN}_{client.account_id}_last_gas_cost",
            "OVO Last Gas Cost",
            "mdi:cash-multiple",
            currency,
        )

    async def _ovo_energy_update(self) -> bool:
        """Update OVO Energy entity."""
        await self._coordinator.async_request_refresh()
        usage: OVODailyUsage = self._coordinator.data
        if usage is None or usage.gas is None:
            _LOGGER.warning("No data found for %s", self._name)
            self._available = False
            return False
        last_reading: OVODailyElectricity = usage.gas[len(usage.gas) - 1]
        self._state = last_reading.cost.amount
        self._attributes = {
            "start_time": last_reading.interval.start,
            "end_time": last_reading.interval.end,
        }
        self._available = True
        return True
