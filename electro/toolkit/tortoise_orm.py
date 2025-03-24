"""The `tortoise-orm` configuration module."""

import ssl
import typing

import stringcase
from tortoise import Tortoise
from tortoise.backends.base.config_generator import expand_db_url
from tortoise.models import Model as tortoise_Model
from tortoise.models import ModelMeta as tortoise_ModelMeta

from ..settings import settings


class ModelMeta(tortoise_ModelMeta):
    """
    Metaclass for `tortoise-orm` `Model`.

    We set the correct default DB table name in here.
    """

    # TODO: [3/9/2023 by Mykola] Automatically set the `through` attribute for
    #  `fields.ManyToManyField` (now it's done manually in `models.py`)

    def __new__(mcs, name, bases, attrs):
        """Create a new `Model` class."""
        new_class: typing.Type[tortoise_Model] = super().__new__(mcs, name, bases, attrs)

        if name != "Model":
            # Cache the `._meta` attribute, so we don't have to access it multiple times
            # noinspection PyProtectedMember
            meta = new_class._meta

            if not meta.db_table:
                meta.db_table = stringcase.snakecase(name)

        return new_class


class Model(tortoise_Model, metaclass=ModelMeta):
    """The base `tortoise-orm` `Model`."""

    pass


def get_tortoise_config():
    """Get the configuration for the `tortoise-orm`."""
    if not settings.DATABASE_URL:
        database_url = (
            f"postgres://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
            f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
    else:
        database_url = str(settings.DATABASE_URL)

    db = expand_db_url(database_url)
    ctx = False
    if settings.ENABLE_DATABASE_SSL:
        ctx = ssl.create_default_context(cafile="")
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    db["credentials"]["ssl"] = ctx

    tortoise_config = {
        "connections": {"default": db},
        "apps": {
            "electro": {
                "models": [
                    "electro.models",
                    "aerich.models",
                ],
                "default_connection": "default",
            }
        },
    }
    return tortoise_config


async def init():
    """Initialize the `tortoise-orm`."""
    # Init database connection
    await Tortoise.init(config=get_tortoise_config())


async def shutdown():
    """Shutdown the `tortoise-orm`."""
    await Tortoise.close_connections()


# Used by aerich.ini
TORTOISE_ORM_CONFIG = get_tortoise_config()


def flatten_tortoise_model(model: tortoise_Model, separator: str | None = ".", prefix: str | None = None) -> dict:
    """Flatten a `tortoise-orm` `Model` to a dictionary with a given separator in the keys."""
    flattened_dict: dict = {}
    for key, value in model.__dict__.items():
        if isinstance(value, tortoise_Model):
            flattened_dict.update(
                **flatten_tortoise_model(
                    value,
                    separator=separator,
                    prefix=f"{key.removeprefix('_')}{separator}",
                )
            )
        # Do not return internal properties of the `Model`
        elif key.startswith("_"):
            pass
        else:
            flattened_dict.setdefault(key, value)

    if prefix:
        flattened_dict = {f"{prefix}{k}": v for k, v in flattened_dict.items()}

    # always return the same result
    return dict(sorted(flattened_dict.items(), key=lambda x: x[0]))
