# core/session.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    eposta: str
    rol: str          # 'admin' | 'koordinator'
    bolum_id: Optional[int]  # admin -> None, koordinator -> int

current_user: Optional[User] = None

def login_as(user: User) -> None:
    global current_user
    current_user = user

def logout() -> None:
    global current_user
    current_user = None

def require_role(*roles: str) -> None:
    if current_user is None or current_user.rol not in roles:
        raise PermissionError("Bu sayfaya erişim izniniz yok.")



