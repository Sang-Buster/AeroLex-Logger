#!/usr/bin/env python3
"""
VR Flight Training Backend Startup Script
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    """Start the VR training backend server"""

    backend_dir = Path(__file__).parent / "backend"

    if not backend_dir.exists():
        print("❌ Backend directory not found")
        sys.exit(1)

    # Change to backend directory
    os.chdir(backend_dir)

    # Check for SSL certificate
    cert_dir = Path(__file__).parent / "certs"
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"

    use_https = cert_file.exists() and key_file.exists()

    print("🚀 Starting VR Flight Training Backend...")
    print(f"📁 Working directory: {backend_dir}")

    if use_https:
        print("🔒 HTTPS enabled (required for VR headset access)")
        print("🌐 Web interface: https://localhost:8000/static")
        print("📖 API docs: https://localhost:8000/docs")
        print(
            "⚠️  You may see a security warning - click 'Advanced' and proceed (self-signed cert)"
        )
    else:
        print("⚠️  Running on HTTP - VR headset access will NOT work!")
        print("🔒 To enable HTTPS (required for VR), run:")
        print("   python3 generate_cert.py")
        print("🌐 Web interface: http://localhost:8000/static")
        print("📖 API docs: http://localhost:8000/docs")
    print()

    try:
        # Check if uv is available (preferred)
        uv_available = False
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            uv_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        # Start the backend server
        if uv_available:
            print("📦 Using uv to run uvicorn...")
            cmd = [
                "uv",
                "run",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",  # Changed from 127.0.0.1 to allow VR headset access
                "--port",
                "8000",
                "--reload",
                "--reload-dir",
                ".",
            ]
        else:
            print("🐍 Using system Python to run uvicorn...")
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                "--reload",
                "--reload-dir",
                ".",
            ]

        if use_https:
            cmd.extend(
                [
                    "--ssl-keyfile",
                    str(key_file),
                    "--ssl-certfile",
                    str(cert_file),
                ]
            )

        subprocess.run(cmd, check=True)

    except KeyboardInterrupt:
        print("\n👋 Backend server stopped")

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start backend server: {e}")
        sys.exit(1)

    except FileNotFoundError:
        print("❌ uvicorn not found. Please install backend dependencies:")
        print("   cd backend && pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
