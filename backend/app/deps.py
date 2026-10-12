from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.security import decode_access_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Identity always comes from the signed session cookie, never from request bodies or params."""
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise unauthorized
    user_id = decode_access_token(token)
    if not user_id:
        raise unauthorized
    user = db.get(User, user_id)
    if not user:
        raise unauthorized
    return user