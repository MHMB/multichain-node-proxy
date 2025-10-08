#!/usr/bin/env python3
"""
Test script for date filtering functionality in multi-blockchain API.
Tests the date-to-block conversion and parameter passing.
"""

import sys
from datetime import datetime
from app.services.ethereum_service import EthereumService
from app.services.bnb_service import BnbService

def test_date_parsing():
    """Test date parsing and conversion to timestamps"""
    print("=" * 60)
    print("Testing Date Parsing")
    print("=" * 60)

    test_dates = [
        "2024-01-01",
        "2024-01-31",
        "2024-01-01T00:00:00",
        "2024-01-31T23:59:59",
    ]

    for date_str in test_dates:
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            timestamp = int(dt.timestamp())
            print(f"✓ {date_str:25} -> Timestamp: {timestamp}")
        except Exception as e:
            print(f"✗ {date_str:25} -> Error: {e}")

    print()

def test_ethereum_service():
    """Test Ethereum service date conversion (without making actual API calls)"""
    print("=" * 60)
    print("Testing Ethereum Service - Date to Block Conversion Logic")
    print("=" * 60)

    try:
        service = EthereumService()
        print("✓ EthereumService initialized successfully")

        # Test the conversion method with sample dates (will use defaults if API fails)
        start_block, end_block = service._convert_dates_to_blocks(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )

        print(f"  Date range: 2024-01-01 to 2024-01-31")
        print(f"  Start block: {start_block}")
        print(f"  End block: {end_block}")

        # Test with no dates (should return defaults)
        start_block_default, end_block_default = service._convert_dates_to_blocks()
        print(f"\n  No dates provided:")
        print(f"  Start block: {start_block_default} (default)")
        print(f"  End block: {end_block_default} (default)")

        if start_block_default == 0 and end_block_default == 99999999:
            print("✓ Default block range is correct")

    except Exception as e:
        print(f"✗ Error testing Ethereum service: {e}")
        import traceback
        traceback.print_exc()

    print()

def test_bnb_service():
    """Test BNB service date conversion (without making actual API calls)"""
    print("=" * 60)
    print("Testing BNB Service - Date to Block Conversion Logic")
    print("=" * 60)

    try:
        service = BnbService()
        print("✓ BnbService initialized successfully")

        # Test the conversion method with sample dates
        start_block, end_block = service._convert_dates_to_blocks(
            start_date="2024-01-01",
            end_date="2024-01-31"
        )

        print(f"  Date range: 2024-01-01 to 2024-01-31")
        print(f"  Start block: {start_block}")
        print(f"  End block: {end_block}")

        # Test with no dates (should return defaults)
        start_block_default, end_block_default = service._convert_dates_to_blocks()
        print(f"\n  No dates provided:")
        print(f"  Start block: {start_block_default} (default)")
        print(f"  End block: {end_block_default} (default)")

        if start_block_default == 0 and end_block_default == 99999999:
            print("✓ Default block range is correct")

    except Exception as e:
        print(f"✗ Error testing BNB service: {e}")
        import traceback
        traceback.print_exc()

    print()

def test_method_signatures():
    """Test that all services have consistent method signatures"""
    print("=" * 60)
    print("Testing Method Signatures for Consistency")
    print("=" * 60)

    from app.services.tron_service import TronService
    from app.services.solana_service import SolanaService
    import inspect

    services = [
        ("EthereumService", EthereumService),
        ("BnbService", BnbService),
        ("TronService", TronService),
        ("SolanaService", SolanaService),
    ]

    for service_name, service_class in services:
        try:
            # Get the signature of get_transactions_list
            sig = inspect.signature(service_class.get_transactions_list)
            params = list(sig.parameters.keys())

            expected_params = ['self', 'wallet_address', 'limit', 'token', 'start_date', 'end_date']

            if params == expected_params:
                print(f"✓ {service_name:20} has correct signature")
            else:
                print(f"✗ {service_name:20} signature mismatch")
                print(f"  Expected: {expected_params}")
                print(f"  Got:      {params}")
        except Exception as e:
            print(f"✗ {service_name:20} error: {e}")

    print()

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("DATE FILTERING IMPLEMENTATION TEST SUITE")
    print("=" * 60 + "\n")

    test_date_parsing()
    test_method_signatures()
    test_ethereum_service()
    test_bnb_service()

    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print("\nNote: These tests verify the implementation logic.")
    print("To test with real blockchain data, you need to:")
    print("1. Ensure API keys are configured in .env")
    print("2. Start the server with: uvicorn app.main:app --reload")
    print("3. Use the API endpoints with date parameters")
    print("\nExample API call:")
    print('  GET /transactions_list?wallet_address=0x123...&blockchain=ethereum')
    print('      &limit=20&start_date=2024-01-01&end_date=2024-01-31')

if __name__ == "__main__":
    main()
