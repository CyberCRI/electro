from typing import Optional

import jwt
from fastapi import Cookie, Header, HTTPException

from .enums import SupportedPlatforms
from .models import PlatformId, User
from .settings import settings


async def authenticate_user(
    platform: str,
    user_id: str,
    header: Optional[str] = Header(default=None, alias="Authorization"),
    cookie: Optional[str] = Cookie(default=None, alias="IKIGAI_AUTHORIZATION"),
) -> User:
    """Validate the Bearer token provided in the request header or in the cookie."""
    # Determine the authentication method based on the platform
    authentication_method = {client: "jwt" for client in settings.JWT_PLATFORMS}.get(platform, "api_key")

    # Validate the platform
    if platform not in SupportedPlatforms:
        raise HTTPException(status_code=400, detail=f"Platform {platform} is not supported.")

    # Get the authorization token from the header or cookie
    authorization = header or cookie
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header or IKIGAI_AUTHORIZATION cookie is required.")
    if header and authentication_method == "jwt":
        if not authorization.startswith(f"{settings.JWT_TOKEN_TYPE} "):
            raise HTTPException(status_code=401, detail=f"Authorization header type must be {settings.JWT_TOKEN_TYPE}")
        authorization = authorization.split(" ")[1]

    if authentication_method == "api_key":
        return await _api_key_authenticate_user(platform, user_id, authorization)
    return await _jwt_authenticate_user(platform, authorization)


async def _get_or_create_user(platform: str, user_id: str, username: Optional[str] = None) -> User:
    """Get or create a user based on the platform and user ID."""
    platform_id, created = await PlatformId.get_or_create(
        platform_id=user_id, platform=platform, type=PlatformId.PlatformIdTypes.USER
    )
    if created:
        user = await User.create(username=username or user_id)
        platform_id.user = user
        await platform_id.save()
    return await platform_id.user


async def _api_key_authenticate_user(platform: str, user_id: str, api_key: str) -> User:
    """Validate the API key provided in the request header."""
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return await _get_or_create_user(platform, user_id)


async def _jwt_authenticate_user(platform: str, token: str) -> User:
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

    return await _get_or_create_user(platform, user_id, username)
