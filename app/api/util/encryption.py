"""
AES-256 encryption helpers for PII fields (guardian/parent email).
"""
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from app.api.core.config import settings

BLOCK_SIZE = 32  # 256 bits


def _get_key_iv():
    key = settings.ENCRYPTION_KEY.encode("utf-8")
    salt = settings.ENCRYPTION_SALT.encode("utf-8")
    # Key must be 32 bytes, IV 16 bytes
    key = key[:32].ljust(32, b"0")
    iv = salt[:16].ljust(16, b"0")
    return key, iv


def encrypt_email(plain_email: str) -> str:
    key, iv = _get_key_iv()
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(BLOCK_SIZE * 8).padder()
    padded_data = padder.update(plain_email.encode("utf-8")) + padder.finalize()
    ct = encryptor.update(padded_data) + encryptor.finalize()
    return base64.urlsafe_b64encode(ct).decode("utf-8")


def decrypt_email(encrypted_email: str) -> str:
    if not encrypted_email or not isinstance(encrypted_email, (str, bytes)):
        return None
    key, iv = _get_key_iv()
    backend = default_backend()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    decryptor = cipher.decryptor()
    ct = base64.urlsafe_b64decode(
        encrypted_email.encode("utf-8") if isinstance(encrypted_email, str) else encrypted_email
    )
    padded_data = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(BLOCK_SIZE * 8).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data.decode("utf-8")
