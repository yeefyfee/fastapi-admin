"""
请求体加解密中间件（双向 AES-256-GCM）。

请求方向:
  Client: JSON → encrypt → Base64 → HTTP body + X-Encrypted: true
  Server: decrypt → 注入原始 JSON → 路由处理

响应方向:
  Server: JSON → encrypt → Base64 → HTTP body
  Client: Base64 decode → decrypt → 原始 JSON

触发条件：请求头 X-Encrypted: true
解密/加密失败返回 400/500，透传非加密请求。
"""
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from src.base.crypto.cipher import RequestCrypto


class CryptoMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, key: bytes):
        super().__init__(app)
        self.crypto = RequestCrypto(key)

    async def dispatch(self, request: Request, call_next):
        encrypted = request.headers.get("X-Encrypted", "").lower() == "true"

        # ── 请求解密 ──
        if encrypted and request.method not in ("GET", "HEAD", "OPTIONS"):
            try:
                raw_body = await request.body()
                if raw_body:
                    plaintext = self.crypto.decrypt(raw_body.decode())

                    async def receive():
                        return {"type": "http.request", "body": plaintext, "more_body": False}

                    request._receive = receive
                    request._body = plaintext
                    request.state.decrypted_body = json.loads(plaintext)
            except Exception:
                return JSONResponse(
                    {"detail": "请求解密失败，请检查加密密钥是否匹配"},
                    status_code=400,
                )

        response = await call_next(request)

        # ── 响应加密 ──
        if encrypted and response.status_code < 400:
            try:
                body = b""
                # 读取响应体
                if hasattr(response, "body"):
                    body = response.body
                else:
                    async for chunk in response.body_iterator:
                        body += chunk

                encrypted_body = self.crypto.encrypt(body)
                return Response(
                    content=encrypted_body,
                    status_code=response.status_code,
                    headers={**dict(response.headers), "X-Encrypted": "true", "content-type": "text/plain"},
                )
            except Exception:
                return JSONResponse(
                    {"detail": "响应加密失败"},
                    status_code=500,
                )

        return response
