"""The API server that works as an endpoint for all the Electro Interfaces."""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import register_tortoise

from . import types_ as types
from .chat_router import chat__router
from .flow_manager import global_flow_manager
from .settings import settings
from .toolkit.tortoise_orm import get_tortoise_config

app = FastAPI(
    title="Electro API",
    description="The API server that works as an endpoint for all the Electro Interfaces.",
    version="0.1.0",
    # docs_url="/",
    # redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        # Allow http or https, with or without port, with or without subdomain
        rf"(http|https)://.*{settings.DOMAIN.split(':', maxsplit=1)[0]}(:\d+)*"
        if settings.DEBUG
        # Allow all subdomains of the main domain, but only https
        # pylint: disable=anomalous-backslash-in-string
        else rf"https:\/\/.*\.?{'\.'.join(settings.DOMAIN.split('.')[-2:])}"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/message")
async def process_message(message: types.Message) -> list[types.MessageToSend] | None:
    """Process the message."""

    return await global_flow_manager.on_message(message)


app.include_router(chat__router, prefix="/chat")

# region Register Tortoise
register_tortoise(
    app,
    config=get_tortoise_config(),
)

# endregion
