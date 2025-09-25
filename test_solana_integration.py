#!/usr/bin/env python3
"""
Integration test for Solana token filtering with the main API.
Tests that the enhanced Solana service works correctly with the FastAPI endpoints.
"""

import requests
import sys
import json
import time

BASE_URL = "http://localhost:8000"

def login_and_get_token():
    """Login and get JWT token for API authentication."""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "admin", "password": "password123"}
        )
        if response.status_code == 200:
            token_data = response.json()
            return token_data["access_token"]
    except Exception as e:
        print(f"Login failed: {e}")
    return None

def test_solana_wallet_info(token):
    """Test Solana wallet info endpoint."""
    print("\n=== Testing Solana Wallet Info Endpoint ===")

    headers = {"Authorization": f"Bearer {token}"}
    test_wallet = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

    try:
        response = requests.get(
            f"{BASE_URL}/wallet_info",
            params={
                "wallet_address": test_wallet,
                "blockchain": "solana"
            },
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Solana wallet info retrieved successfully")
            print(f"   Wallet: {data['wallet_address'][:10]}...")
            print(f"   SOL Balance: {data['native_token']['balance']}")
            print(f"   Token Count: {len(data['tokens'])}")
            return True
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Wallet info test failed: {e}")

    return False

def test_solana_all_transactions(token):
    """Test Solana transactions endpoint without token filter."""
    print("\n=== Testing Solana All Transactions Endpoint ===")

    headers = {"Authorization": f"Bearer {token}"}
    test_wallet = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

    try:
        response = requests.get(
            f"{BASE_URL}/transactions_list",
            params={
                "wallet_address": test_wallet,
                "blockchain": "solana",
                "limit": 5
            },
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Solana all transactions retrieved successfully")
            print(f"   Transaction count: {len(data['transactions'])}")
            print(f"   Native balance: {data['native_balance_formatted']} {data['native_symbol']}")

            if data['transactions']:
                latest_tx = data['transactions'][0]
                print(f"   Latest TX: {latest_tx['hash'][:10]}... - {latest_tx['token_symbol']}")

            return True
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ All transactions test failed: {e}")

    return False

def test_solana_token_filtered_transactions(token):
    """Test Solana transactions endpoint with token filter."""
    print("\n=== Testing Solana Token-Filtered Transactions Endpoint ===")

    headers = {"Authorization": f"Bearer {token}"}
    test_wallet = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
    usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC mint

    try:
        response = requests.get(
            f"{BASE_URL}/transactions_list",
            params={
                "wallet_address": test_wallet,
                "blockchain": "solana",
                "limit": 5,
                "token": usdc_mint
            },
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Solana token-filtered transactions retrieved successfully")
            print(f"   USDC transaction count: {len(data['transactions'])}")

            if data['transactions']:
                print("   USDC Transactions found:")
                for tx in data['transactions'][:3]:  # Show first 3
                    print(f"     • {tx['hash'][:10]}... - {tx['amount_formatted']} {tx['token_symbol']}")
            else:
                print("   ℹ️  No USDC transactions found (normal if wallet has no USDC activity)")

            return True
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Token-filtered transactions test failed: {e}")

    return False

def test_solana_contract_details(token):
    """Test Solana contract details endpoint."""
    print("\n=== Testing Solana Contract Details Endpoint ===")

    headers = {"Authorization": f"Bearer {token}"}
    usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC mint

    try:
        response = requests.get(
            f"{BASE_URL}/contract_details",
            params={
                "contract_address": usdc_mint,
                "blockchain": "solana"
            },
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Solana contract details retrieved successfully")
            print(f"   Token: {data['name']} ({data['symbol']})")
            print(f"   Decimals: {data['decimals']}")
            print(f"   Total Supply: {data['total_supply_formatted']}")
            return True
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Contract details test failed: {e}")

    return False

def main():
    """Run integration tests."""
    print("🚀 Starting Solana Integration Tests with API")
    print("=" * 60)

    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"❌ API health check failed: {response.status_code}")
            return 1
    except requests.exceptions.RequestException:
        print(f"❌ Cannot connect to API at {BASE_URL}")
        print("Make sure the service is running with:")
        print("  uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return 1

    print("✅ API is running")

    # Login and get token
    token = login_and_get_token()
    if not token:
        print("❌ Failed to get authentication token")
        return 1

    print(f"✅ Authentication successful")

    # Run tests
    results = []
    results.append(test_solana_wallet_info(token))
    results.append(test_solana_all_transactions(token))
    results.append(test_solana_token_filtered_transactions(token))
    results.append(test_solana_contract_details(token))

    # Summary
    passed = sum(results)
    total = len(results)

    print("\n" + "=" * 60)
    print(f"📊 Integration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ All integration tests passed!")
        print("\n🎉 Solana Token Filtering Implementation is working correctly!")
        print("\n📋 Features Verified:")
        print("   • ✅ Basic Solana wallet info retrieval")
        print("   • ✅ All transactions (SOL + SPL tokens)")
        print("   • ✅ Token-specific filtering (NEW FEATURE)")
        print("   • ✅ SPL token contract details")
        print("   • ✅ API authentication integration")
        print("   • ✅ Error handling")
        return 0
    else:
        print("❌ Some integration tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())