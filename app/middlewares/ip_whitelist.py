import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Middleware to restrict API access to specific IP addresses.
    Reads allowed IPs from environment variables.
    """
    
    def __init__(self, app):
        super().__init__(app)
        # Support both single IP and comma-separated list
        allowed_ips_env = os.getenv("ALLOWED_IPS", "")
        if allowed_ips_env:
            self.allowed_ips = [ip.strip() for ip in allowed_ips_env.split(",") if ip.strip()]
        else:
            self.allowed_ips = []
    
    async def dispatch(self, request: Request, call_next):
        # Skip IP check for health check endpoint
        if request.url.path == "/":
            return await call_next(request)
        
        # If no IPs configured, allow all
        if not self.allowed_ips:
            return await call_next(request)
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Check if IP is allowed
        if client_ip not in self.allowed_ips:
            raise HTTPException(
                status_code=403,
                detail="Access denied: IP address not allowed"
            )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers."""
        # Check for forwarded IP first (for reverse proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
