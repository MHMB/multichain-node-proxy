#!/usr/bin/env python3
"""
Test script to demonstrate response model compatibility checking.
Run this script to validate your API responses and check for breaking changes.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.responses import (
    WalletInfoResponse, 
    TransactionsListResponse, 
    ContractDetailsResponse,
    NativeToken,
    WalletToken,
    Transaction
)
from app.models.compatibility import compatibility_checker, check_api_compatibility
import json


def test_response_validation():
    """Test response validation with sample data."""
    print("=== Testing Response Validation ===\n")
    
    # Sample wallet info data
    wallet_info_data = {
        "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
        "blockchain": "ethereum",
        "native_token": {
            "symbol": "ETH",
            "decimals": 18,
            "balance": 1.5
        },
        "tokens": [
            {
                "token_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
                "name": "USD Coin",
                "symbol": "USDC",
                "decimals": 6,
                "balance": 1000.0
            }
        ]
    }
    
    # Test valid data
    try:
        wallet_response = WalletInfoResponse(**wallet_info_data)
        print("✅ WalletInfoResponse validation passed")
        print(f"   Wallet: {wallet_response.wallet_address}")
        print(f"   Blockchain: {wallet_response.blockchain}")
        print(f"   Native token: {wallet_response.native_token.symbol} - {wallet_response.native_token.balance}")
        print(f"   Token count: {len(wallet_response.tokens)}")
    except Exception as e:
        print(f"❌ WalletInfoResponse validation failed: {e}")
    
    print()
    
    # Test invalid data
    invalid_data = {
        "wallet_address": "",  # Empty address should fail
        "blockchain": "bitcoin",  # Unsupported blockchain
        "native_token": {
            "symbol": "ETH",
            "decimals": 18,
            "balance": -1.0  # Negative balance should fail
        },
        "tokens": []
    }
    
    try:
        WalletInfoResponse(**invalid_data)
        print("❌ Invalid data validation should have failed")
    except Exception as e:
        print("✅ Invalid data correctly rejected")
        print(f"   Error: {e}")
    
    print()


def test_compatibility_checking():
    """Test compatibility checking functionality."""
    print("=== Testing Compatibility Checking ===\n")
    
    # Generate compatibility report
    report = check_api_compatibility()
    print("API Compatibility Report:")
    print(json.dumps(report, indent=2))
    print()
    
    # Test individual model compatibility
    for model_name in compatibility_checker.response_models.keys():
        print(f"Testing {model_name}:")
        model_report = compatibility_checker.generate_compatibility_report(model_name)
        print(f"  Versions: {model_report['versions']}")
        print(f"  Breaking changes: {len(model_report['breaking_changes'])}")
        print()


def test_service_response_validation():
    """Test service response validation."""
    print("=== Testing Service Response Validation ===\n")
    
    from app.models.compatibility import validate_service_response
    
    # Sample service responses
    sample_responses = {
        "wallet_info": {
            "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
            "blockchain": "ethereum",
            "native_token": {
                "symbol": "ETH",
                "decimals": 18,
                "balance": 1.5
            },
            "tokens": []
        },
        "transactions_list": {
            "blockchain": "ethereum",
            "wallet_address": "0x1234567890abcdef1234567890abcdef12345678",
            "native_balance": "1500000000000000000",
            "native_balance_formatted": "1.500000000000000000",
            "native_symbol": "ETH",
            "tokens": [],
            "transactions": []
        },
        "contract_details": {
            "contract_address": "0xA0b86a33E6441b8C4C8C0C4C0C4C0C4C0C4C0C4C",
            "blockchain": "ethereum",
            "name": "USD Coin",
            "symbol": "USDC",
            "decimals": 6,
            "total_supply": "1000000000000000",
            "total_supply_formatted": "1000000000.000000",
            "creator": "",
            "creation_time": "",
            "verified": True,
            "holder_count": 0,
            "transfer_count": 0,
            "is_mintable": False,
            "is_burnable": False
        }
    }
    
    for endpoint, data in sample_responses.items():
        try:
            is_valid = validate_service_response("test_service", endpoint, data)
            print(f"✅ {endpoint}: {'Valid' if is_valid else 'Invalid'}")
        except Exception as e:
            print(f"❌ {endpoint}: Error - {e}")
    
    print()


def demonstrate_type_safety():
    """Demonstrate type safety features."""
    print("=== Demonstrating Type Safety ===\n")
    
    # Test with proper types
    native_token = NativeToken(symbol="ETH", decimals=18, balance=1.5)
    print(f"✅ NativeToken created: {native_token.symbol} - {native_token.balance}")
    
    # Test transaction with proper field aliasing
    transaction_data = {
        "hash": "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        "timestamp": "2024-01-15T10:30:00Z",
        "from": "0xSenderAddress1234567890abcdef1234567890abcdef",  # Note: 'from' not 'from_'
        "to": "0xRecipientAddress1234567890abcdef1234567890ab",
        "amount": "1000000000000000000",
        "amount_formatted": "1.0",
        "token_symbol": "ETH",
        "transaction_fee": "21000000000000000",
        "transaction_fee_formatted": "0.021",
        "status": "success",
        "block_number": 12345678
    }
    
    try:
        transaction = Transaction(**transaction_data)
        print(f"✅ Transaction created: {transaction.hash[:10]}...")
        print(f"   From: {transaction.from_[:10]}...")  # Access via from_ attribute
    except Exception as e:
        print(f"❌ Transaction creation failed: {e}")
    
    print()


if __name__ == "__main__":
    print("🚀 Starting Response Model Compatibility Tests\n")
    
    test_response_validation()
    test_compatibility_checking()
    test_service_response_validation()
    demonstrate_type_safety()
    
    print("✅ All tests completed!")

