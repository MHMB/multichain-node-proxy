"""
Database models for request/response logging.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Dict, Any

Base = declarative_base()


class RequestLog(Base):
    """Model for storing request/response logs."""

    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(String(45), nullable=False)  # IPv6 compatible
    user_id = Column(String(100), nullable=True)  # From JWT token
    method = Column(String(10), nullable=False)  # GET, POST, etc.
    endpoint = Column(String(500), nullable=False)  # Request path
    query_params = Column(JSON, nullable=True)  # Query parameters as JSON
    headers = Column(JSON, nullable=True)  # Request headers as JSON
    request_body = Column(JSON, nullable=True)  # Request body as JSON
    response_status = Column(Integer, nullable=False)  # HTTP status code
    response_body = Column(JSON, nullable=True)  # Response data as JSON
    response_time_ms = Column(Float, nullable=False)  # Response time in milliseconds
    blockchain = Column(String(20), nullable=True)  # Target blockchain
    wallet_address = Column(String(100), nullable=True)  # Target wallet address
    error_message = Column(Text, nullable=True)  # Error message if any

    def __repr__(self):
        return f"<RequestLog(id={self.id}, method={self.method}, endpoint={self.endpoint}, status={self.response_status})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address,
            'user_id': self.user_id,
            'method': self.method,
            'endpoint': self.endpoint,
            'query_params': self.query_params,
            'headers': self.headers,
            'request_body': self.request_body,
            'response_status': self.response_status,
            'response_body': self.response_body,
            'response_time_ms': self.response_time_ms,
            'blockchain': self.blockchain,
            'wallet_address': self.wallet_address,
            'error_message': self.error_message
        }