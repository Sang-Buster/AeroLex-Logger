#!/usr/bin/env python3
"""
Generate self-signed SSL certificate for local HTTPS development.
Required for WebXR/VR headset access.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Generate self-signed SSL certificate"""

    project_root = Path(__file__).parent
    cert_dir = project_root / "certs"
    cert_file = cert_dir / "cert.pem"
    key_file = cert_dir / "key.pem"

    # Create certs directory
    cert_dir.mkdir(exist_ok=True)

    print("🔒 Generating self-signed SSL certificate...")
    print(f"📁 Certificate directory: {cert_dir}")
    print()

    # Check if certificates already exist
    if cert_file.exists() and key_file.exists():
        response = input("⚠️  Certificates already exist. Regenerate? (y/N): ")
        if response.lower() != "y":
            print("✅ Using existing certificates")
            return
        print("♻️  Regenerating certificates...")

    try:
        # Generate self-signed certificate using openssl
        cmd = [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:4096",
            "-nodes",
            "-out",
            str(cert_file),
            "-keyout",
            str(key_file),
            "-days",
            "365",
            "-subj",
            "/C=US/ST=State/L=City/O=VR-Training/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:0.0.0.0",
        ]

        subprocess.run(cmd, check=True, capture_output=True)

        print("✅ SSL certificate generated successfully!")
        print()
        print("📋 Certificate files:")
        print(f"   🔑 Private key: {key_file}")
        print(f"   📜 Certificate: {cert_file}")
        print()
        print("🚀 Next steps:")
        print("   1. Start the backend server: python3 start_backend.py")
        print("   2. Accept the security warning in your browser (self-signed cert)")
        print("   3. Connect your VR headset to the same network")
        print("   4. Open https://YOUR_COMPUTER_IP:8000/static in VR browser")
        print()
        print("💡 To find your computer's IP address:")
        print("   Linux/Mac: ifconfig | grep 'inet '")
        print("   Windows: ipconfig | findstr 'IPv4'")
        print()

    except FileNotFoundError:
        print("❌ OpenSSL not found!")
        print()
        print("Please install OpenSSL:")
        print("   Ubuntu/Debian: sudo apt-get install openssl")
        print("   macOS: brew install openssl")
        print(
            "   Windows: Download from https://slproweb.com/products/Win32OpenSSL.html"
        )
        sys.exit(1)

    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate certificate: {e}")
        print(e.stderr.decode() if e.stderr else "")
        sys.exit(1)


if __name__ == "__main__":
    main()
