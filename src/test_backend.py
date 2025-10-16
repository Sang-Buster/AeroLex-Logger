#!/usr/bin/env python3
"""
Test script to verify backend functionality
"""

import sys

import requests


def test_backend():
    """Test backend endpoints"""

    base_url = "http://127.0.0.1:8000"

    print("🧪 Testing VR Flight Training Backend...")
    print(f"📍 Base URL: {base_url}")

    try:
        # Test health endpoint
        print("\n1. Testing health endpoint...")
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False

        # Test video initialization
        print("\n2. Testing video initialization...")
        response = requests.post(f"{base_url}/api/v1/videos/initialize", timeout=10)
        if response.status_code == 200:
            print("✅ Video initialization passed")
            result = response.json()
            print(f"   Response: {result}")
        else:
            print(f"❌ Video initialization failed: {response.status_code}")
            if response.text:
                print(f"   Error: {response.text}")
            return False

        # Test student login
        print("\n3. Testing student login...")
        login_data = {"name": "Test Student", "student_id": "TEST001"}
        response = requests.post(
            f"{base_url}/api/v1/auth/login", json=login_data, timeout=5
        )
        if response.status_code == 200:
            print("✅ Student login passed")
            result = response.json()
            print(
                f"   Student: {result['student']['name']} (ID: {result['student']['student_id']})"
            )
        else:
            print(f"❌ Student login failed: {response.status_code}")
            if response.text:
                print(f"   Error: {response.text}")
            return False

        # Test getting videos for student
        print("\n4. Testing get videos for student...")
        response = requests.get(f"{base_url}/api/v1/videos/student/TEST001", timeout=5)
        if response.status_code == 200:
            print("✅ Get videos passed")
            result = response.json()
            print(f"   Found {len(result['videos'])} videos")
            if result["videos"]:
                first_video = result["videos"][0]
                print(
                    f"   First video: {first_video['title']} (unlocked: {first_video['unlocked']})"
                )
        else:
            print(f"❌ Get videos failed: {response.status_code}")
            if response.text:
                print(f"   Error: {response.text}")
            return False

        print("\n✅ All tests passed! Backend is working correctly.")
        return True

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Is it running on http://127.0.0.1:8000?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Backend request timed out")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    success = test_backend()
    sys.exit(0 if success else 1)
