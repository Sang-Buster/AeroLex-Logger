#!/usr/bin/env python3
"""
Video Completion Test Script

This script helps you test the video completion tracking system.
It can:
1. Simulate video completion POST requests to the external server
2. Check student progress and scores
3. Generate test data

Usage:
    python test_video_completion.py --help
"""

import argparse
import json

import requests

# Configuration
BASE_API_URL = "http://localhost:8000"
EXTERNAL_SERVER_URL = "http://150.136.241.0:5000/uploadVideoResults"


def test_video_completion(
    student_id: str,
    video_number: int,
    watch_percent: float = 95,
    similarity: float = 85,
):
    """
    Simulate a video completion POST request to external server.

    Args:
        student_id: Student ID (7 digits)
        video_number: Video index (0-based)
        watch_percent: Percentage of video watched (0-100)
        similarity: Average similarity score (0-100)
    """
    payload = {
        "id": student_id,
        "videoNumber": video_number,
        "status": "1",
        "similarity": f"{similarity:.2f}",
        "watchPercentage": f"{watch_percent:.2f}",
    }

    print(f"\n{'=' * 70}")
    print("🧪 Testing Video Completion")
    print(f"{'=' * 70}")
    print(f"Student ID: {student_id}")
    print(f"Video Number: {video_number}")
    print(f"Watch Percentage: {watch_percent:.1f}%")
    print(f"Avg Similarity: {similarity:.1f}%")
    print(f"\nPayload: {json.dumps(payload, indent=2)}")

    # 1. Update local database first
    print("\n💾 Updating local database...")
    try:
        # Get video ID from index
        videos_response = requests.get(f"{BASE_API_URL}/api/v1/videos/").json()
        if videos_response.get("videos") and video_number < len(
            videos_response["videos"]
        ):
            video_id = videos_response["videos"][video_number]["id"]

            # Update progress
            progress_url = f"{BASE_API_URL}/api/v1/students/{student_id}/progress"
            progress_data = {
                "video_id": video_id,
                "completed": True,
                "score": similarity / 100,  # Convert to 0-1 range
            }
            progress_response = requests.post(progress_url, json=progress_data)

            if progress_response.ok:
                print("✅ Local database updated")
            else:
                print(
                    f"⚠️ Local database update failed: {progress_response.status_code}"
                )
        else:
            print(f"⚠️ Video {video_number} not found in database")
    except Exception as e:
        print(f"⚠️ Error updating local database: {e}")

    # 2. Send to external server
    try:
        print(f"\n📤 Sending POST to {EXTERNAL_SERVER_URL}...")
        response = requests.post(EXTERNAL_SERVER_URL, json=payload, timeout=10)

        print(f"✅ Response Status: {response.status_code}")

        if response.ok:
            try:
                data = response.json()
                print(f"✅ Server Response: {json.dumps(data, indent=2)}")
                return data
            except Exception:
                print(f"✅ Server Response: {response.text}")
                return response.text
        else:
            print(f"❌ Error Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: {e}")
        return None


def check_student_progress(student_id: str):
    """
    Check student progress from the local API.

    Args:
        student_id: Student ID (7 digits)
    """
    print(f"\n{'=' * 70}")
    print("📊 Checking Student Progress")
    print(f"{'=' * 70}")

    try:
        # Get dashboard data
        print("\n📈 Fetching dashboard data...")
        dashboard_url = f"{BASE_API_URL}/api/v1/students/{student_id}/dashboard"
        dashboard = requests.get(dashboard_url).json()

        print("✅ Dashboard Data:")
        print(f"   Total Videos: {dashboard.get('total_videos', 0)}")
        print(f"   Completed: {dashboard.get('completed_videos', 0)}")
        print(f"   Average Score: {dashboard.get('average_score', 0) * 100:.1f}%")

        # Get statistics
        print("\n📊 Fetching statistics...")
        stats_url = f"{BASE_API_URL}/api/v1/students/{student_id}/statistics"
        stats = requests.get(stats_url).json()

        print("✅ Statistics:")
        print(
            f"   Total Time Spent: {stats.get('total_time_spent', 0) / 60:.1f} minutes"
        )
        print(f"   Total Attempts: {stats.get('total_attempts', 0)}")

        # Get progress details
        print("\n🎬 Fetching video progress...")
        progress_url = f"{BASE_API_URL}/api/v1/students/{student_id}/progress"
        progress = requests.get(progress_url).json()

        if progress.get("progress"):
            print(f"\n{'Video':<40} {'Completed':<12} {'Score':<10} {'Attempts':<10}")
            print(f"{'-' * 70}")
            for p in progress["progress"]:
                video_id = p.get("video_id", "Unknown")
                completed = "✅" if p.get("completed") else "❌"
                score = f"{p.get('best_score', 0) * 100:.1f}%"
                attempts = p.get("attempt_count", 0)
                print(f"{video_id:<40} {completed:<12} {score:<10} {attempts:<10}")

        return {"dashboard": dashboard, "stats": stats, "progress": progress}

    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        return None


def test_multiple_completions(student_id: str, count: int = 3):
    """
    Test multiple video completions with random data.

    Args:
        student_id: Student ID (7 digits)
        count: Number of videos to simulate
    """
    import random

    print(f"\n{'=' * 70}")
    print(f"🧪 Testing Multiple Video Completions ({count} videos)")
    print(f"{'=' * 70}")

    results = []
    for i in range(count):
        watch_percent = random.uniform(90, 100)
        similarity = random.uniform(50, 100)

        print(f"\n📹 Video {i}:")
        result = test_video_completion(student_id, i, watch_percent, similarity)
        results.append(result)

        # Wait a bit between requests
        import time

        time.sleep(1)

    print(f"\n✅ All {count} tests completed!")
    return results


def main():
    parser = argparse.ArgumentParser(description="Test video completion tracking")
    parser.add_argument("student_id", help="Student ID (7 digits)")
    parser.add_argument(
        "--video", type=int, default=0, help="Video number/index (default: 0)"
    )
    parser.add_argument(
        "--watch", type=float, default=95.0, help="Watch percentage (default: 95)"
    )
    parser.add_argument(
        "--similarity", type=float, default=85.0, help="Similarity score (default: 85)"
    )
    parser.add_argument(
        "--multiple", type=int, help="Test multiple videos (specify count)"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check student progress only"
    )

    args = parser.parse_args()

    print("""
╔════════════════════════════════════════════════════════════════════════╗
║          VIDEO COMPLETION TEST SCRIPT                                  ║
╚════════════════════════════════════════════════════════════════════════╝
    """)

    if args.check:
        # Just check progress
        check_student_progress(args.student_id)
    elif args.multiple:
        # Test multiple completions
        test_multiple_completions(args.student_id, args.multiple)
        print("\n" + "=" * 70)
        check_student_progress(args.student_id)
    else:
        # Test single completion
        test_video_completion(args.student_id, args.video, args.watch, args.similarity)
        print("\n" + "=" * 70)
        check_student_progress(args.student_id)


if __name__ == "__main__":
    main()
