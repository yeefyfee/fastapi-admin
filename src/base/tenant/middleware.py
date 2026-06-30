from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from src.base.tenant.deps import current_tenant_id


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = request.headers.get("X-Tenant-ID")
        token = current_tenant_id.set(tenant_id)
        try:
            response = await call_next(request)
        finally:
            current_tenant_id.reset(token)
        return response
