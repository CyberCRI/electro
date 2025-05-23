from typing import Optional

import jwt
from fastapi import Header, HTTPException, Query

from .enums import SupportedPlatforms
from .models import PlatformId, User
from .settings import settings


async def http_authenticate_user(
    platform: str, user_id: str, authorization: Optional[str] = Header(default=None)
) -> User:
    """Validate the Bearer token provided in the request header."""
    if not authorization.startswith(f"{settings.JWT_TOKEN_TYPE} "):
        raise HTTPException(status_code=401, detail=f"Authorization header type must be {settings.JWT_TOKEN_TYPE}")
    token = authorization.split(" ")[1]
    return await _authenticate_user(platform, user_id, token)


async def ws_authenticate_user(platform: str, user_id: str, token: Optional[str] = Query(default=None)) -> User:
    """Validate the Bearer token provided in the request header."""
    return await _authenticate_user(platform, user_id, token)


async def _authenticate_user(platform: str, user_id: str, token: Optional[str] = None) -> User:
    if platform not in SupportedPlatforms:
        raise HTTPException(status_code=400, detail=f"Platform {platform} is not supported.")
    if settings.AUTHENTICATION_ENABLED:
        try:
            validated_token = jwt.decode(token, settings.JWT_KEY, algorithms=["RS256"], options={"verify_aud": False})
        except jwt.ExpiredSignatureError as e:
            raise HTTPException(status_code=401, detail="Token has expired") from e
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail="Invalid token") from e
        user_id = validated_token.get(settings.JWT_ID_KEY)
        username = validated_token.get(settings.JWT_USERNAME_KEY)
        if not user_id or not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        username = user_id  # TODO: Find a better solution to pass the username
    platform_id, created = await PlatformId.get_or_create(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if created:
        user = await User.create(username=username)
        platform_id.user = user
        await platform_id.save()
    return await platform_id.user
