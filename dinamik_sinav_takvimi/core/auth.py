



#core/auth.py

from __future__ import annotations

import os
import hmac
import hashlib
from typing import Tuple

try:
    import bcrypt  # type: ignore
    BCRYPT_AVAILABLE = True
except Exception:
    bcrypt = None
    BCRYPT_AVAILABLE = False

def _to_bytes(s: str | bytes) -> bytes:
    return s if isinstance(s, bytes) else s.encode("utf-8")


def _is_bcrypt_hash(h: str) -> bool:
    return isinstance(h, str) and h.startswith(("$2a$", "$2b$", "$2y$"))


def _is_pbkdf2_hash(h: str) -> bool:
    return isinstance(h, str) and h.startswith("pbkdf2$")


def _pbkdf2_hash(plain: str | bytes, salt: bytes | None = None, iterations: int = 120_000) -> Tuple[str, bytes, bytes]:
    """PBKDF2-HMAC(SHA-256) ile hash oluşturur."""
    pwd = _to_bytes(plain)
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pwd, salt, iterations)
    return f"pbkdf2${salt.hex()}${dk.hex()}", salt, dk


def _pbkdf2_verify(plain: str | bytes, stored: str, iterations: int = 120_000) -> bool:
    """'pbkdf2$<salt>$<hash>' formatını doğrular."""
    try:
        _, salt_hex, hash_hex = stored.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        _, _, dk = _pbkdf2_hash(plain, salt=salt, iterations=iterations)
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def hash_password(plain: str) -> str:
    """
    Varsayılan: bcrypt (varsa).
    Yoksa: PBKDF2-HMAC(SHA-256).

    DÖNÜŞ:
      - bcrypt -> "$2b$..." metni
      - pbkdf2 -> "pbkdf2$<salt_hex>$<hash_hex>"
    """
    if not isinstance(plain, (str, bytes)):
        raise TypeError("plain must be str or bytes")

    if BCRYPT_AVAILABLE:
        pwd = _to_bytes(plain)
        return bcrypt.hashpw(pwd, bcrypt.gensalt()).decode("utf-8")  
    else:
        hashed, _, _ = _pbkdf2_hash(plain)
        return hashed


def check_password(plain: str, stored_hash: str) -> bool:
    """
    `stored_hash` hangi formatta ise ona göre doğrular.
    Destek: bcrypt, pbkdf2, legacy-plain (eşitlik karşılaştırması).
    """
    if stored_hash is None:
        return False

    
    if _is_bcrypt_hash(stored_hash):
        if not BCRYPT_AVAILABLE:
        
            return False
        try:
            return bcrypt.checkpw(_to_bytes(plain), _to_bytes(stored_hash))  
        except Exception:
            return False

    if _is_pbkdf2_hash(stored_hash):
        return _pbkdf2_verify(plain, stored_hash)

    
    try:
        return hmac.compare_digest(_to_bytes(plain), _to_bytes(stored_hash))
    except Exception:
        return False


def needs_rehash(stored_hash: str) -> bool:
    """
    Şifre hashinin yeniden üretilmesi gerekip gerekmediğini söyler.
    Kriterler:
      - Düz metin ise: True
      - PBKDF2 ise ve bcrypt mevcutsa: True (tercihen bcrypt'e geç)
      - Bcrypt ise: False (opsiyonel olarak maliyet faktörü kontrolü eklenebilir)
    """
    if not stored_hash:
        return True
    if _is_bcrypt_hash(stored_hash):
        return False
    if _is_pbkdf2_hash(stored_hash):
        return BCRYPT_AVAILABLE 
   
    return True


def maybe_upgrade_hash(plain: str, stored_hash: str) -> str | None:
    """
    Doğrulama sonrası, daha iyi bir formata yükseltmek istersen çağır:
      - Eğer needs_rehash True ise yeni hash döner (örn. bcrypt),
      - Aksi halde None döner.
    """
    if needs_rehash(stored_hash):
        try:
            return hash_password(plain)
        except Exception:
            return None
    return None
