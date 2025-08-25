#!/usr/bin/env python3
"""
Test script for the Multi-Blockchain API with authentication.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint (no auth required)."""
    print("1. Testing health check endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"   Error: {e}")
        return False

def test_unauthorized_access():
    """Test accessing protected endpoint without authentication."""
    print("\n2. Testing unauthorized access (should return 401)...")
    try:
        response = requests.get(
            f"{BASE_URL}/wallet_info",
            params={
                "wallet_address": "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
                "blockchain": "ethereum"
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returned 401 Unauthorized")
            return True
        else:
            print("   ❌ Expected 401 but got different status")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

def login(username="admin", password="password123"):
    """Login and get JWT token."""
    print(f"\n3. Logging in as {username}...")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": username, "password": password}
        )
        if response.status_code == 200:
            token_data = response.json()
            token = token_data["access_token"]
            print(f"   ✅ Login successful")
            print(f"   Token: {token[:20]}...")
            return token
        else:
            print(f"   ❌ Login failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"   Error: {e}")
        return None

def test_authenticated_request(token):
    """Test protected endpoint with valid token."""
    print("\n4. Testing authenticated request...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/wallet_info",
            params={
                "wallet_address": "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
                "blockchain": "ethereum"
            },
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Authenticated request successful")
            # Print first few lines of response
            response_text = response.text
            lines = response_text.split('\n')[:5]
            print(f"   Response preview: {lines}")
            return True
        else:
            print(f"   ❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

def test_invalid_token():
    """Test with invalid token."""
    print("\n5. Testing with invalid token (should return 401)...")
    try:
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = requests.get(
            f"{BASE_URL}/wallet_info",
            params={
                "wallet_address": "0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae",
                "blockchain": "ethereum"
            },
            headers=headers
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 401:
            print("   ✅ Correctly returned 401 for invalid token")
            return True
        else:
            print("   ❌ Expected 401 but got different status")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

def test_user_info(token):
    """Test user info endpoint."""
    print("\n6. Testing user info endpoint...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            user_info = response.json()
            print(f"   ✅ User info retrieved: {user_info}")
            return True
        else:
            print(f"   ❌ Failed to get user info")
            return False
    except Exception as e:
        print(f"   Error: {e}")
        return False

def main():
    """Run all tests."""
    print("=== Multi-Blockchain API Authentication Tests ===")
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
    except requests.exceptions.RequestException:
        print(f"❌ Cannot connect to API at {BASE_URL}")
        print("Make sure the service is running with:")
        print("  docker-compose up -d")
        print("  or")
        print("  uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    results = []
    
    # Run tests
    results.append(test_health_check())
    results.append(test_unauthorized_access())
    
    token = login()
    if token:
        results.append(test_authenticated_request(token))
        results.append(test_invalid_token())
        results.append(test_user_info(token))
    else:
        print("❌ Cannot continue tests without valid token")
        sys.exit(1)
    
    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n=== Test Summary ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
