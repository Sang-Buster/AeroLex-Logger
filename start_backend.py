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
    
    print("🚀 Starting VR Flight Training Backend...")
    print(f"📁 Working directory: {backend_dir}")
    print("🌐 Web interface will be available at: http://localhost:8000/static")
    print("📖 API docs will be available at: http://localhost:8000/docs")
    print()
    
    try:
        # Start the backend server
        subprocess.run([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--reload",
            "--reload-dir", "."
        ], check=True)
        
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
