"""
Middleware for logging requests and responses to database.
"""
import time
import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import db_manager
from app.models.database import RequestLog
from app.config import Config

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses to database."""

    def __init__(self, app, log_requests: bool = True, log_response_body: bool = True, log_request_headers: bool = False):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_response_body = log_response_body
        self.log_request_headers = log_request_headers

    async def dispatch(self, request: Request, call_next):
        if not self.log_requests:
            return await call_next(request)

        # Start timing
        start_time = time.time()

        # Extract request information
        request_data = await self._extract_request_data(request)

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000

        # Extract response information
        response_data = await self._extract_response_data(response)

        # Log to database asynchronously
        try:
            await self._log_to_database(request_data, response_data, response_time_ms)
        except Exception as e:
            logger.error(f"Failed to log request to database: {e}")

        return response

    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """Extract relevant data from request."""
        # Get client IP
        client_ip = self._get_client_ip(request)

        # Get user ID if available
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = getattr(request.state.user, 'username', None)

        # Get query parameters
        query_params = dict(request.query_params) if request.query_params else None

        # Get headers (filtered for security)
        headers = None
        if self.log_request_headers:
            headers = self._filter_headers(dict(request.headers))

        # Get request body for POST/PUT requests
        request_body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    # Try to parse as JSON
                    try:
                        request_body = json.loads(body.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_body = {"raw_body": body.decode(errors='replace')}
            except Exception as e:
                logger.warning(f"Could not read request body: {e}")

        # Extract blockchain and wallet info from query params
        blockchain = query_params.get('blockchain') if query_params else None
        wallet_address = query_params.get('wallet_address') if query_params else None

        return {
            'ip_address': client_ip,
            'user_id': user_id,
            'method': request.method,
            'endpoint': str(request.url.path),
            'query_params': query_params,
            'headers': headers,
            'request_body': request_body,
            'blockchain': blockchain,
            'wallet_address': wallet_address
        }

    async def _extract_response_data(self, response: Response) -> Dict[str, Any]:
        """Extract relevant data from response."""
        response_body = None
        error_message = None

        if self.log_response_body and hasattr(response, 'body'):
            try:
                if isinstance(response, StreamingResponse):
                    # For streaming responses, we can't easily capture the body
                    response_body = {"type": "streaming_response"}
                else:
                    body = response.body
                    if body:
                        try:
                            response_body = json.loads(body.decode())
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            response_body = {"raw_body": body.decode(errors='replace')}
            except Exception as e:
                error_message = f"Failed to capture response body: {str(e)}"

        # Capture error messages for non-200 status codes
        if response.status_code >= 400 and not error_message:
            if response_body and isinstance(response_body, dict):
                error_message = response_body.get('detail', f"HTTP {response.status_code}")
            else:
                error_message = f"HTTP {response.status_code}"

        return {
            'response_status': response.status_code,
            'response_body': response_body,
            'error_message': error_message
        }

    async def _log_to_database(self, request_data: Dict[str, Any], response_data: Dict[str, Any], response_time_ms: float):
        """Log request/response data to database."""
        try:
            async with db_manager.get_session() as session:
                log_entry = RequestLog(
                    ip_address=request_data['ip_address'],
                    user_id=request_data['user_id'],
                    method=request_data['method'],
                    endpoint=request_data['endpoint'],
                    query_params=request_data['query_params'],
                    headers=request_data['headers'],
                    request_body=request_data['request_body'],
                    response_status=response_data['response_status'],
                    response_body=response_data['response_body'],
                    response_time_ms=response_time_ms,
                    blockchain=request_data['blockchain'],
                    wallet_address=request_data['wallet_address'],
                    error_message=response_data['error_message']
                )

                session.add(log_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Database logging failed: {e}")
            raise

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address from request."""
        # Check X-Forwarded-For header first (for proxies/load balancers)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            # Take the first IP in case of multiple IPs
            return forwarded_for.split(',')[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip.strip()

        # Fall back to client host
        if request.client:
            return request.client.host

        return "unknown"

    def _filter_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Filter sensitive headers from logging."""
        sensitive_headers = {
            'authorization',
            'cookie',
            'x-api-key',
            'x-auth-token',
            'authorization-key'
        }

        filtered = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                filtered[key] = "***REDACTED***"
            else:
                filtered[key] = value

        return filtered