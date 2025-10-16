#!/usr/bin/env python3
"""
Video Cleanup Script
Renames video files to a cleaner naming convention

Usage:
    python cleanup_videos_simple.py --dry-run     # Show planned changes
    python cleanup_videos_simple.py --execute     # Execute without prompts
    python cleanup_videos_simple.py               # Interactive mode (default)
    python cleanup_videos_simple.py test          # Test regex patterns
"""

import argparse
import re
import sys
from pathlib import Path


def create_clean_filename(original_name):
    """
    Convert original filename to clean format
    Examples:
    '01-1 - 7L Depature North.mp4' -> '7L_Departure_North.mp4'
    '04-1 - 7R Rose Arrival South.mp4' -> '7R_Arrival_South.mp4'
    '08 - 1 - Cross Country to St. Augistine_Part 1.mp4' -> 'Cross_Country_to_St_Augustine_Part_1.mp4'
    '01_7L_Departure_North.mp4' -> '7L_Departure_North.mp4' (already clean, just remove number prefix)
    """
    # Remove file extension
    name = Path(original_name).stem

    # Check if already in clean format (starts with number_)
    if re.match(r"^\d+_", name):
        # Already in clean format, just remove the number prefix
        name = re.sub(r"^\d+_", "", name)
        return name

    # Remove the number prefix with flexible spacing patterns for old format
    # Handles: 01-1-, 01 - 1 -, 01 - 1-, 01-1 -, 08 - 1 -, etc.
    name = re.sub(r"^\d+\s*-\s*\d+\s*-\s*", "", name)

    # Fix common typos
    name = name.replace("Depature", "Departure")
    name = name.replace("St. Augistine", "St_Augustine")
    name = name.replace("St. Augustine", "St_Augustine")

    # Remove extra words
    name = name.replace("Rose ", "")  # Remove "Rose" from "7R Rose Arrival South"

    # Replace spaces and hyphens with underscores
    name = name.replace(" ", "_").replace("-", "_")

    # Clean up multiple underscores
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    return name


def main():
    """Main cleanup function"""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Clean up video file names")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without executing them",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Execute the renaming without prompting"
    )
    args = parser.parse_args()

    script_dir = Path(__file__).parent.parent
    videos_dir = script_dir / "videos"

    if not videos_dir.exists():
        print(f"❌ Videos directory not found: {videos_dir}")
        return

    # Get all video files and sort them
    video_files = []
    for ext in [".mp4", ".mov", ".avi", ".mkv"]:
        video_files.extend(list(videos_dir.glob(f"*{ext}")))

    video_files.sort(key=lambda x: x.name)

    print(f"🎬 Found {len(video_files)} video files")

    if not video_files:
        print("⚠️  No video files found to rename")
        return

    print("📋 Planned renamings:")
    print("-" * 80)

    # Plan the renamings
    rename_plan = []
    for i, video_file in enumerate(video_files, 1):
        old_name = video_file.name
        clean_name = create_clean_filename(old_name)
        new_name = f"{i:02d}_{clean_name}{video_file.suffix}"

        rename_plan.append(
            {"old_path": video_file, "new_name": new_name, "old_name": old_name}
        )

        print(f"{i:2d}. '{old_name}'")
        print(f"    -> '{new_name}'")
        print()

    # Check if this is a dry run
    if args.dry_run:
        print("🔍 This is a dry run. No files will be renamed.")
        return

    # Ask for confirmation unless --execute is specified
    if not args.execute:
        print("-" * 80)
        try:
            response = (
                input(f"❓ Rename {len(rename_plan)} video files? (y/N): ")
                .strip()
                .lower()
            )
            if response != "y":
                print("❌ Renaming cancelled")
                return
        except (EOFError, KeyboardInterrupt):
            print("\n❌ Renaming cancelled")
            return

    # Perform video renaming
    print(f"\n🎬 Renaming {len(rename_plan)} video files...")
    renamed_count = 0

    for item in rename_plan:
        old_path = item["old_path"]
        new_path = old_path.parent / item["new_name"]

        try:
            if new_path.exists():
                print(f"⚠️  Target exists, skipping: {item['new_name']}")
                continue

            if old_path.name == item["new_name"]:
                print(f"⏭️  Already correctly named: {item['new_name']}")
                continue

            old_path.rename(new_path)
            print(f"✅ Renamed: {item['old_name']} -> {item['new_name']}")
            renamed_count += 1
        except Exception as e:
            print(f"❌ Error renaming {item['old_name']}: {e}")

    print(f"\n✅ Video cleanup completed! Renamed {renamed_count} files.")

    if renamed_count > 0:
        print("\n📋 Final video list:")
        print("-" * 50)
        # List all video files after renaming
        video_files_after = []
        for ext in [".mp4", ".mov", ".avi", ".mkv"]:
            video_files_after.extend(list(videos_dir.glob(f"*{ext}")))
        video_files_after.sort(key=lambda x: x.name)

        for i, video_file in enumerate(video_files_after, 1):
            print(f"  {i:2d}. {video_file.name}")


def test_patterns():
    """Test function to verify the regex handles various patterns"""
    test_cases = [
        # Old format with various spacing patterns
        "01-1 - 7L Departure North.mp4",
        "01 - 1 - 7L Departure North.mp4",
        "01 - 1- 7L Departure North.mp4",
        "01-1- 7L Departure North.mp4",
        "08-3 - Cross Country to St. Augistine_Part 2.mp4",
        "08 - 3 - Cross Country to St. Augustine_Part 2.mp4",
        # Already clean format
        "01_7L_Departure_North.mp4",
        "05_Cross_Country_to_St_Augustine_Part_1.mp4",
    ]

    print("🧪 Testing filename patterns:")
    print("-" * 60)

    for test_case in test_cases:
        clean = create_clean_filename(test_case)
        print(f"'{test_case}'")
        print(f"  -> '{clean}'")
        print()


if __name__ == "__main__":
    # Check if user wants to test patterns
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_patterns()
    else:
        main()
