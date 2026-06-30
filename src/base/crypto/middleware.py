"""
请求体加解密中间件。

触发条件：请求头 X-Encrypted: true
解密失败返回 400，透传非加密请求。
"""
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from src.base.crypto.cipher import RequestCrypto


class CryptoMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, key: bytes):
        super().__init__(app)
        self.crypto = RequestCrypto(key)

    async def dispatch(self, request: Request, call_next):
        if request.headers.get("X-Encrypted", "").lower() != "true":
            return await call_next(request)

        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        try:
            raw_body = await request.body()
            if not raw_body:
                return await call_next(request)

            encrypted_text = raw_body.decode()
            plaintext = self.crypto.decrypt(encrypted_text)
            body_json = json.loads(plaintext)

            # 构造带解密后 body 的新请求
            async def receive():
                return {"type": "http.request", "body": plaintext, "more_body": False}

            request._receive = receive
            request._body = plaintext
            request.state.decrypted_body = body_json
        except Exception:
            return JSONResponse(
                {"detail": "请求解密失败，请检查加密密钥是否匹配"},
                status_code=400,
            )

        return await call_next(request)
