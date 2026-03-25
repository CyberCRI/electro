"""The extra Storage Substitutions for the `electro` Framework."""

from abc import ABC
from typing import Any, cast, Type

from ..flow_connector import FlowConnector
from ..substitutions import BaseSubstitution, CallbackSubstitution
from ..toolkit.tortoise_orm import Model
from .storage_buckets import BaseStorageBucketElement


class TortoiseModelSubstitution(CallbackSubstitution, ABC):
    """A substitution that gets a value from a Tortoise model."""

    def __init__(
        self,
        tortoise_model: Type[Model],
        tortoise_model_field_name: str,
        filters: dict[str, Any] | None = None,
        ordering: str = "",
        ensure_list_result: bool = False,
        **kwargs,
    ):
        """Initialize the substitution."""
        self.tortoise_model = tortoise_model
        self.tortoise_model_field_name = tortoise_model_field_name
        self.filters = filters or {}
        self.ordering = ordering
        self.ensure_list_result = ensure_list_result

        super().__init__(callback=self.get_value_for_connector, **kwargs)

    @staticmethod
    async def resolve_filters(flow_connector: FlowConnector, filters: dict[str, Any]) -> dict[str, Any]:
        return {
            key: (
                await value.get_data(default=value._type())  # pylint: disable=W0212
                if isinstance(value, BaseStorageBucketElement)
                else await value.resolve(flow_connector) if isinstance(value, BaseSubstitution) else value
            )
            for key, value in filters.items()
        }

    async def get_value_for_connector(self, flow_connector: FlowConnector) -> str | list[str]:
        """Get the value from the Tortoise model."""

        filters: dict[str, Any] = await self.resolve_filters(flow_connector, self.filters)

        if self.ordering:
            value = (
                await self.tortoise_model
                .filter(**filters)
                .order_by(self.ordering)
                .values_list(self.tortoise_model_field_name, flat=True)
            )
        else:
            value = await self.tortoise_model.filter(**filters).values_list(self.tortoise_model_field_name, flat=True)        
        if isinstance(value, list) and len(value) >= 1 and not self.ensure_list_result:
            return cast(str, value[0])

        return cast(list, value)
