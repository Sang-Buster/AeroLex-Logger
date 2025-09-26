#!/usr/bin/env python3
"""
VR Flight Training ASR Service Startup Script
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    """Start the VR ASR service"""
    
    parser = argparse.ArgumentParser(description="Start VR ASR Service")
    parser.add_argument("--student-id", required=True, help="Student ID")
    parser.add_argument("--video-id", help="Video ID")
    parser.add_argument("--session-id", help="Session ID")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--device", type=int, help="Audio device ID")
    
    args = parser.parse_args()
    
    # Get the project root directory
    project_root = Path(__file__).parent
    src_dir = project_root / "src"
    vr_asr_script = src_dir / "asr_service_vr.py"
    
    if not vr_asr_script.exists():
        print(f"❌ VR ASR script not found: {vr_asr_script}")
        sys.exit(1)
    
    # Prepare command
    cmd = [sys.executable, str(vr_asr_script)]
    
    # Add arguments
    cmd.extend(["--student-id", args.student_id])
    
    if args.video_id:
        cmd.extend(["--video-id", args.video_id])
    
    if args.session_id:
        cmd.extend(["--session-id", args.session_id])
    
    if args.debug:
        cmd.append("--debug")
    
    if args.device is not None:
        cmd.extend(["--device", str(args.device)])
    
    print("🎤 Starting VR Flight Training ASR Service...")
    print(f"👤 Student ID: {args.student_id}")
    if args.video_id:
        print(f"🎬 Video ID: {args.video_id}")
    if args.session_id:
        print(f"📊 Session ID: {args.session_id}")
    print()
    
    try:
        # Start the ASR service
        subprocess.run(cmd, check=True, cwd=project_root)
        
    except KeyboardInterrupt:
        print("\n👋 ASR service stopped")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ ASR service failed: {e}")
        sys.exit(1)
        
    except FileNotFoundError:
        print("❌ Python interpreter not found")
        sys.exit(1)

if __name__ == "__main__":
    main()
