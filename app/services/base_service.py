"""
Base service class with enhanced type safety and response validation.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, TypeVar, Generic
from pydantic import BaseModel, ValidationError
import logging

# Type variables for generic service responses
T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseBlockchainService(ABC, Generic[T]):
    """Base class for blockchain services with enhanced type safety."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = None
        self._response_cache: Dict[str, Any] = {}
    
    @abstractmethod
    def get_wallet_info(self, wallet_address: str) -> 'WalletInfoResponse':
        """Get wallet information."""
        pass
    
    @abstractmethod
    def get_transactions_list(self, wallet_address: str, limit: int = 20, token: Optional[str] = None) -> 'TransactionsListResponse':
        """Get transaction list."""
        pass
    
    @abstractmethod
    def get_contract_details(self, contract_address: str) -> 'ContractDetailsResponse':
        """Get contract details."""
        pass
    
    def validate_response(self, response_data: Dict[str, Any], model_class: type[T]) -> T:
        """Validate response data against a Pydantic model."""
        try:
            return model_class(**response_data)
        except ValidationError as e:
            logger.error(f"Response validation failed: {e}")
            raise ValueError(f"Invalid response data: {e}")
    
    def safe_get(self, url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """Safely make HTTP GET request with error handling."""
        try:
            if not self.session:
                import requests
                self.session = requests.Session()
            
            response = self.session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            return None
    
    def safe_post(self, url: str, data: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Optional[Dict[str, Any]]:
        """Safely make HTTP POST request with error handling."""
        try:
            if not self.session:
                import requests
                self.session = requests.Session()
            
            response = self.session.post(url, json=data, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            return None
    
    def cache_response(self, key: str, data: Any, ttl: int = 300) -> None:
        """Cache response data with TTL."""
        import time
        self._response_cache[key] = {
            'data': data,
            'timestamp': time.time(),
            'ttl': ttl
        }
    
    def get_cached_response(self, key: str) -> Optional[Any]:
        """Get cached response if not expired."""
        import time
        if key in self._response_cache:
            cached = self._response_cache[key]
            if time.time() - cached['timestamp'] < cached['ttl']:
                return cached['data']
            else:
                del self._response_cache[key]
        return None

