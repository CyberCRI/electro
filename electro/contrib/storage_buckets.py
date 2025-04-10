"""The module that contains the Storages and Storage Buckets - main data storage units used with the Framework."""

from __future__ import annotations

import typing
from abc import ABC, ABCMeta, abstractmethod
from typing import Generic, get_origin, Type

import tortoise
from stringcase import snakecase

from ..flow_connector import FlowConnector
from ..scopes import FlowScopes
from ..substitutions import BaseSubstitution, VALUE
from ..toolkit.loguru_logging import logger

STORAGE_BUCKETS_SEPARATOR = "::"


class StorageSubstitution(BaseSubstitution):
    """The Substitution object that would be returned from the storage bucket."""

    data_factory: typing.Callable[[], typing.Awaitable[VALUE | None]]
    index: int | None = None

    def __init__(
        self,
        data_factory: typing.Callable[[], typing.Awaitable[VALUE | None]],
        index: int | None = None,
        **kwargs,
    ):
        """Initialize the Storage Substitution."""
        super().__init__(**kwargs)

        self.data_factory = data_factory
        self.index = index

    async def _resolve(self, connector: FlowConnector) -> VALUE:
        """Resolve the substitution object."""
        try:
            data = await self.data_factory()
        except TypeError:
            error_message = f"ERROR: {self.data_factory} is not a callable or awaitable."
            logger.error(error_message)
            return error_message

        if self.index is not None:
            try:
                data = data[self.index]
            except (TypeError, IndexError) as exception:
                return str(f"{exception} in STORAGE SUBSTITUTION for index: {self.index}")

        return data


class StorageData(Generic[VALUE]):
    """The class that stores the data."""

    _data: VALUE | None = None

    def __init__(self, data: VALUE | None = None):
        """Initialize the storage element."""
        self._data = data

    def get(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data for the storage element."""
        return self._data or default

    def set(self, data: VALUE):
        """Set the data for the storage element."""
        self._data = data


# Note: [11.03.2024 by Mykola] There was this other idea that we might use so-called `*Resource`s to get the data
# from/for different scopes. It never got enough traction to be implemented, but here's the draft:`

# class BaseStorageResource(ABC):
#     """Base storage resource class - where the data is stored and how to get it."""
#
#     @abstractmethod
#     async def get_data(self, default: VALUE | None = None) -> VALUE | None:
#         """Get the data for the storage element."""
#         raise NotImplementedError
#
#     @abstractmethod
#     async def set_data(self, data: VALUE):
#         """Set the data for the storage element."""
#         raise NotImplementedError
#
#     async def delete_data(self):
#         """Delete the data for the storage element."""
#         return await self.set_data(None)
#
#
# class UserStorageResource(BaseStorageResource):
#     """A storage resource that gets the data from the user data."""
#
#     async def get_data(self):
#


class BaseStorageBucketElement(Generic[VALUE], ABC):
    """The class for storage elements."""

    _type: type[VALUE]
    _scope: FlowScopes
    _storage_data: StorageData[VALUE] | None

    def __init__(self, *, _type: type[VALUE], _scope: FlowScopes = FlowScopes.USER, **__):
        """Initialize the storage element. Called by the metaclass."""
        self._type = _type
        self._scope = _scope
        self._storage_data = None

    @staticmethod
    async def get_current_user_id() -> int:
        """Get the current user's ID."""
        flow_connector = FlowConnector.get_current()

        return flow_connector.user.id

    @staticmethod
    async def get_current_channel_id() -> int:
        """Get the current channel's ID."""
        flow_connector = FlowConnector.get_current()

        return flow_connector.channel.id

    # region User data methods
    @abstractmethod
    async def _get_user_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data of the storage element when the scope is `USER`."""
        raise NotImplementedError()

    @abstractmethod
    async def _set_user_data(self, data: VALUE):
        """Set the data of the storage element when the scope is `USER`."""
        raise NotImplementedError()

    @abstractmethod
    async def _delete_user_data(self):
        """Delete the data of the storage element when the scope is `USER`."""
        raise NotImplementedError()

    # endregion

    # region Channel data methods
    @abstractmethod
    async def _get_channel_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data of the storage element when the scope is `CHANNEL`."""
        raise NotImplementedError()

    @abstractmethod
    async def _set_channel_data(self, data: VALUE):
        """Set the data of the storage element when the scope is `CHANNEL`."""
        raise NotImplementedError()

    @abstractmethod
    async def _delete_channel_data(self):
        """Delete the data of the storage element when the scope is `CHANNEL`."""
        raise NotImplementedError()

    async def get_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data for the storage element."""
        if self._scope == FlowScopes.USER:
            return await self._get_user_data(default=default)
        if self._scope == FlowScopes.CHANNEL:
            return await self._get_channel_data(default=default)
        raise NotImplementedError(f"Unknown scope: {self._scope}")

    async def set_data(self, data: VALUE):
        """Set the data for the storage element."""
        if self._scope == FlowScopes.USER:
            return await self._set_user_data(data)
        if self._scope == FlowScopes.CHANNEL:
            return await self._set_channel_data(data)
        raise NotImplementedError(f"Unknown scope: {self._scope}")

    async def delete_data(self):
        """Delete the data for the storage element."""
        if self._scope == FlowScopes.USER:
            return await self._delete_user_data()
        if self._scope == FlowScopes.CHANNEL:
            return await self._delete_channel_data()
        raise NotImplementedError(f"Unknown scope: {self._scope}")

    async def __aenter__(self) -> VALUE:
        """Get the data for the storage element."""
        self._storage_data = StorageData(await self.get_data(default=self._type()))

        return self._storage_data

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Update the data for the storage element."""
        if self._storage_data is not None:
            await self.set_data(self._storage_data.get())

        self._storage_data = None

    # Support retrieving the data from the storage element as a substitution by index
    def __getitem__(self, item: int) -> StorageSubstitution:
        """Get the data of the storage element."""
        return StorageSubstitution(data_factory=self.get_data, index=item)


class StorageBucketElement(BaseStorageBucketElement[VALUE]):
    """The class for storage elements."""

    final_fsm_storage_key_name: str
    _type: type[VALUE]

    def __init__(self, _type: type[VALUE], final_fsm_storage_key_name, **kwargs):
        super().__init__(_type=_type, **kwargs)

        self.final_fsm_storage_key_name = final_fsm_storage_key_name

    # region User data methods
    async def _get_user_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data of the storage element when the scope is `USER`."""
        flow_connector = FlowConnector.get_current()

        return flow_connector.user_data.get(self.final_fsm_storage_key_name, default)

    async def _set_user_data(self, data: VALUE):
        """Set the data of the storage element when the scope is `USER`."""
        flow_connector = FlowConnector.get_current()

        flow_connector.user_data[self.final_fsm_storage_key_name] = data

    async def _delete_user_data(self):
        """Delete the data of the storage element when the scope is `USER`."""
        flow_connector = FlowConnector.get_current()

        if self.final_fsm_storage_key_name in flow_connector.user_data:
            del flow_connector.user_data[self.final_fsm_storage_key_name]

    # endregion

    # region Channel data methods
    async def _get_channel_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data of the storage element when the scope is `CHANNEL`."""
        flow_connector = FlowConnector.get_current()

        return flow_connector.channel_data.get(self.final_fsm_storage_key_name, default)

    async def _set_channel_data(self, data: VALUE):
        """Set the data of the storage element when the scope is `CHANNEL`."""
        flow_connector = FlowConnector.get_current()

        flow_connector.channel_data[self.final_fsm_storage_key_name] = data

    async def _delete_channel_data(self):
        """Delete the data of the storage element when the scope is `CHANNEL`."""
        flow_connector = FlowConnector.get_current()

        if self.final_fsm_storage_key_name in flow_connector.channel_data:
            del flow_connector.channel_data[self.final_fsm_storage_key_name]

    # endregion


class PostgresStorageBucketElement(BaseStorageBucketElement[VALUE]):
    """The class for storage elements that are stored in Postgres."""

    model: tortoise.Model
    field_name: str

    final_fsm_storage_key_name: str | None  # Used only for migration from Redis to Postgres

    def __init__(self, _type: type[VALUE], model: tortoise.Model, field_name: str, **kwargs):
        super().__init__(_type=_type, **kwargs)

        self.model = model
        self.field_name = field_name

        self.final_fsm_storage_key_name: str | None = kwargs.get("final_fsm_storage_key_name", None)

    # region User data methods
    async def _get_user_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data of the storage element when the scope is `USER`."""
        raise NotImplementedError("Get the data of the storage using the `.get_data()` method.")

    async def _set_user_data(self, data: VALUE):
        """Set the data of the storage element when the scope is `USER`."""
        raise NotImplementedError("Set the data of the storage using the `.set_data()` method.")

    async def _delete_user_data(self):
        """Delete the data of the storage element when the scope is `USER`."""
        raise NotImplementedError("Delete the data of the storage using the `.delete_data()` method.")

    # endregion

    # region Channel data methods
    async def _get_channel_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data of the storage element when the scope is `CHANNEL`."""
        raise NotImplementedError("Get the data of the storage using the `.get_data()` method.")

    async def _set_channel_data(self, data: VALUE):
        """Set the data of the storage element when the scope is `CHANNEL`."""
        raise NotImplementedError("Set the data of the storage using the `.set_data()` method.")

    async def _delete_channel_data(self):
        """Delete the data of the storage element when the scope is `CHANNEL`."""
        raise NotImplementedError("Delete the data of the storage using the `.delete_data()` method.")

    # endregion

    async def _get_current_model_instance(self, create_if_not_exists: bool = False) -> tortoise.Model | None:
        """Get the current model instance."""
        if self._scope == FlowScopes.USER:
            param_name = "user_id"
            param_value = await self.get_current_user_id()
        elif self._scope == FlowScopes.CHANNEL:
            param_name = "channel_id"
            param_value = await self.get_current_channel_id()
        else:
            raise NotImplementedError(f"Unknown scope: {self._scope}")

        model_instance = await self.model.get_or_none(**{param_name: param_value})

        if model_instance is None and create_if_not_exists:
            model_instance = await self.model.create(**{param_name: param_value})

        return model_instance

    async def get_data(self, default: VALUE | None = None) -> VALUE | None:
        """Get the data for the storage element."""
        model_instance = await self._get_current_model_instance()

        if model_instance is None:
            return default

        return getattr(model_instance, self.field_name, default) or default

    async def set_data(self, data: VALUE):
        """Set the data for the storage element."""
        model_instance = await self._get_current_model_instance(create_if_not_exists=True)

        setattr(model_instance, self.field_name, data)
        await model_instance.save()

    async def delete_data(self):
        """Delete the data for the storage element."""
        model_instance = await self._get_current_model_instance()

        if model_instance is not None:
            setattr(model_instance, self.field_name, None)
            await model_instance.save()


def _get_all_bases(cls):
    bases = list(cls.__bases__)
    for base in cls.__bases__:
        bases.extend(_get_all_bases(base))
    return bases


class StorageBucketMeta(ABCMeta):
    """The metaclass for storage buckets."""

    def _get_storage_scope(
        cls, storage_element: BaseStorageBucketElement, *, default: FlowScopes = FlowScopes.USER
    ) -> FlowScopes:
        """Get the storage scope."""
        return getattr(cls, "_scope", getattr(storage_element, "_scope", default))

    def __new__(mcs, name, bases, namespace, **kwargs):
        """Create a new storage bucket."""
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        cls._fsm_storage_key_name = snakecase(name)

        if namespace.get(f"_{name}__abstract", False):
            return cls

        merged_bases_annotations = {}
        for cls_base in [_cls_base for base_cls in bases for _cls_base in _get_all_bases(base_cls)]:
            if not issubclass(cls_base, cls):
                continue

            merged_bases_annotations.update(cls_base.__annotations__)

        # Set the storage elements from annotations
        for attr_name, attr_type in (merged_bases_annotations | cls.__annotations__).items():
            if (not attr_name.startswith("_")) and get_origin(attr_type) == StorageBucketElement:
                setattr(
                    cls,
                    attr_name,
                    StorageBucketElement(
                        final_fsm_storage_key_name=(
                            f"{cls._fsm_storage_key_name}{STORAGE_BUCKETS_SEPARATOR}{attr_name}"
                        ),
                        _type=attr_type.__args__[0],
                        _scope=cls._get_storage_scope(attr_type),
                    ),
                )

        return cls


class BaseStorageBucket(ABC, metaclass=StorageBucketMeta):
    """The base class for storage buckets."""

    _fsm_storage_key_name: str
    _scope: FlowScopes = FlowScopes.USER

    def __init__(self, fsm_storage_key_name: str | None = None, _scope: FlowScopes = None):
        """Initialize the storage bucket. Apparently never used directly."""

        self._fsm_storage_key_name = fsm_storage_key_name or self._fsm_storage_key_name
        self._scope = _scope or self._scope

    @classmethod
    async def empty(cls):
        """Empty the storage bucket."""
        flow_connector = FlowConnector.get_current()

        for key in list(flow_connector.user_data.keys()):
            if key.startswith(cls._fsm_storage_key_name):
                del flow_connector.user_data[key]

    @classmethod
    def parse_from_user_data(cls, user_data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Parse the storage bucket from the user data."""
        return {
            key.removeprefix(f"{cls._fsm_storage_key_name}{STORAGE_BUCKETS_SEPARATOR}"): value
            for key, value in user_data.items()
            if key.startswith(f"{cls._fsm_storage_key_name}{STORAGE_BUCKETS_SEPARATOR}")
        }


# region Postgres storage buckets
class PostgresStorageBucketMeta(StorageBucketMeta):
    """The metaclass for Postgres storage buckets."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        """Create a new storage bucket."""
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        cls._fsm_storage_key_name = snakecase(name)

        if namespace.get(f"_{name}__abstract", False):
            return cls

        merged_bases_annotations = {}
        for cls_base in [_cls_base for base_cls in bases for _cls_base in _get_all_bases(base_cls)]:
            if not issubclass(cls_base, BaseStorageBucket):
                continue

            merged_bases_annotations.update(cls_base.__annotations__)

        # Set the storage elements from annotations
        for attr_name, attr_type in (merged_bases_annotations | cls.__annotations__).items():
            resolved_annotations = typing.get_type_hints(cls)
            attr_type = resolved_annotations.get(attr_name, attr_type)
            if (not attr_name.startswith("_")) and issubclass(get_origin(attr_type), BaseStorageBucketElement):
                element_class: Type[PostgresStorageBucketElement] = (
                    PostgresStorageBucketElement
                    if attr_type == StorageBucketElement  # So that the old storage buckets would still work
                    else get_origin(attr_type)
                )

                setattr(
                    cls,
                    attr_name,
                    element_class(
                        _type=attr_type.__args__[0],
                        _scope=cls._get_storage_scope(attr_type),
                        model=cls._model,
                        field_name=attr_name,
                        final_fsm_storage_key_name=(
                            f"{cls._fsm_storage_key_name}{STORAGE_BUCKETS_SEPARATOR}{attr_name}"
                        ),
                    ),
                )

        return cls


class BasePostgresStorageBucket(BaseStorageBucket, metaclass=PostgresStorageBucketMeta):
    """The base class for Postgres storage buckets."""

    __abstract = True  # pylint: disable=W0238

    _model: tortoise.Model

    @classmethod
    async def empty(cls):
        flow_connector = FlowConnector.get_current()

        await cls._model.filter(user_id=flow_connector.user.id).delete()

    # _tortoise_meta: tortoise.models.ModelMeta

    # @classmethod
    # async def describe(cls) -> dict[str, typing.Any]:
    #     """Describe the storage bucket."""
    #     return {
    #         "name": cls._meta.full_name,
    #         "app": cls._meta.app,
    #         "table": cls._meta.db_table,
    #         "abstract": cls._meta.abstract,
    #         "description": cls._meta.table_description or None,
    #         "docstring": inspect.cleandoc(cls.__doc__ or "") or None,
    #         "unique_together": cls._meta.unique_together or [],
    #         "indexes": cls._meta.indexes or [],
    #         "pk_field": cls._meta.fields_map[cls._meta.pk_attr].describe(serializable),
    #         "data_fields": [
    #             field.describe(serializable)
    #             for name, field in cls._meta.fields_map.items()
    #             if name != cls._meta.pk_attr and name in (cls._meta.fields - cls._meta.fetch_fields)
    #         ],
    #         "fk_fields": [
    #             field.describe(serializable)
    #             for name, field in cls._meta.fields_map.items()
    #             if name in cls._meta.fk_fields
    #         ],
    #         "backward_fk_fields": [
    #             field.describe(serializable)
    #             for name, field in cls._meta.fields_map.items()
    #             if name in cls._meta.backward_fk_fields
    #         ],
    #         "o2o_fields": [
    #             field.describe(serializable)
    #             for name, field in cls._meta.fields_map.items()
    #             if name in cls._meta.o2o_fields
    #         ],
    #         "backward_o2o_fields": [
    #             field.describe(serializable)
    #             for name, field in cls._meta.fields_map.items()
    #             if name in cls._meta.backward_o2o_fields
    #         ],
    #         "m2m_fields": [
    #             field.describe(serializable)
    #             for name, field in cls._meta.fields_map.items()
    #             if name in cls._meta.m2m_fields
    #         ],
    #     }


class BaseAssistantsStorageBucket(BaseStorageBucket, ABC):
    """Base storage bucket for the `GPTAssistantStep`s."""

    __abstract = True  # pylint: disable=W0238

    thread_id: StorageBucketElement[str]


class BasePostgresAssistantsStorageBucket(BasePostgresStorageBucket, BaseAssistantsStorageBucket):
    """Base storage bucket for the `GPTAssistantStep`s."""

    __abstract = True  # pylint: disable=W0238


# endregion
