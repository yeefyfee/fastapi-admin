"""
请求体加密/解密工具（AES-256-GCM 双向）。

请求方向:
  Client: JSON → AES-GCM encrypt → Base64 → HTTP body + X-Encrypted: true
  Server: middleware decrypt → 注入原始 JSON → FastAPI routes 正常处理

响应方向:
  Server: JSON response → AES-GCM encrypt → Base64 → HTTP body + X-Encrypted: true
  Client: Base64 decode → AES-GCM decrypt → 原始 JSON
"""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class RequestCrypto:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("AES-256 requires 32-byte key")
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes) -> str:
        """加密 → Base64(nonce + ciphertext)"""
        nonce = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(nonce, plaintext, None)
        return base64.b64encode(nonce + ciphertext).decode()

    def decrypt(self, encrypted: str) -> bytes:
        """解密 Base64(nonce + ciphertext) → 明文"""
        raw = base64.b64decode(encrypted)
        nonce, ciphertext = raw[:12], raw[12:]
        return self._aesgcm.decrypt(nonce, ciphertext, None)
