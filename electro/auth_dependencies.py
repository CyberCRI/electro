"""Authentication dependencies, using JWT."""

# TODO: [2025-07-14 by Mykola] Actually use JWT (or some other authentication method) for User authentication.

from fastapi.requests import Request

from .models import User


async def get_current_user(_request: Request) -> User:
    """Get the current user from the request."""

    return await User.get(id=1)
