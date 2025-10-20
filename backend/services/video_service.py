#!/usr/bin/env python3
"""
Video Management Service
Handles video metadata, ground truth data, and video access control
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from database.sqlite_db import DatabaseManager
from services.evaluation_service import summarize_scores_by_video


class VideoService:
    """Service for managing videos and ground truth data"""

    @staticmethod
    async def initialize_videos():
        """Initialize video database from video files"""
        videos_dir = Path(__file__).parent.parent.parent / "videos"

        if not videos_dir.exists():
            print("⚠️  Videos directory not found")
            return

        # Get all video files
        video_files = [
            f
            for f in videos_dir.iterdir()
            if f.is_file() and f.suffix.lower() in [".mp4", ".mov", ".avi", ".mkv"]
        ]

        # Sort by filename to maintain order
        video_files.sort(key=lambda x: x.name)

        print(f"🎬 Found {len(video_files)} video files")

        async with await DatabaseManager.get_connection() as db:
            for index, video_file in enumerate(video_files, 1):
                video_id = VideoService.generate_video_id(video_file.name)
                title = VideoService.format_video_title(video_file.stem)

                # Check if video already exists
                async with db.execute(
                    "SELECT id FROM videos WHERE id = ?", (video_id,)
                ) as cursor:
                    exists = await cursor.fetchone()

                if not exists:
                    await db.execute(
                        """
                        INSERT INTO videos (id, title, filename, order_index, description)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (video_id, title, video_file.name, index, title),
                    )
                    print(f"📹 Added video {index}: {title}")

            await db.commit()

    @staticmethod
    def generate_video_id(filename: str) -> str:
        """Generate a consistent video ID from filename"""
        # Remove extension
        base_name = Path(filename).stem

        # Handle new naming convention (e.g., "01_7L_Departure_North")
        if "_" in base_name and not base_name.startswith(("01-", "03-", "04-")):
            # New format: use the full filename as ID (lowercased)
            return base_name.lower()

        # Handle old naming convention (e.g., "01-1 - 7L Departure North")
        # Take the first part before the first space or underscore
        clean_name = (
            base_name.split()[0] if " " in base_name else base_name.split("_")[0]
        )
        return clean_name.lower().replace("-", "_")

    @staticmethod
    def format_video_title(filename_stem: str) -> str:
        """Format video title from filename"""
        title = filename_stem

        # Handle new naming convention (e.g., "01_7L_Departure_North")
        if "_" in title and not title.startswith(("01-", "03-", "04-")):
            # New format: remove number prefix and replace underscores with spaces
            title = re.sub(r"^\d+_", "", title)  # Remove "01_" prefix
            title = title.replace("_", " ")
        else:
            # Handle old naming convention (e.g., "01-1 - 7L Departure North")
            # Remove leading numbering like "01-1 - " or "11-3 - "
            title = re.sub(r"^\d+-\d+\s*-\s*", "", title)
            # Replace underscores with spaces
            title = title.replace("_", " ")

        # Capitalize each word but preserve certain patterns
        words = title.split()
        formatted_words = []
        for i, word in enumerate(words):
            # Keep small connector words lowercase (except if first word)
            if i > 0 and word.lower() in {"at", "to", "of", "and", "the"}:
                formatted_words.append(word.lower())
            # Preserve runway designators like "7L", "7R", "25R", etc.
            elif (
                word.upper()
                in [
                    f"{num}{letter}"
                    for num in range(1, 37)
                    for letter in ["L", "R", "C"]
                ]
                or word.upper().endswith(("L", "R", "C"))
                and word[:-1].isdigit()
            ):
                formatted_words.append(word.upper())
            # Preserve common aviation abbreviations
            elif word.upper() in {
                "VFR",
                "IFR",
                "GPS",
                "VOR",
                "ILS",
                "DME",
                "ATC",
                "FSS",
                "CTAF",
                "UNICOM",
                "ATIS",
            }:
                formatted_words.append(word.upper())
            else:
                formatted_words.append(word.capitalize())
        title = " ".join(formatted_words)

        return title

    @staticmethod
    def _convert_to_mixed_case(video_id: str) -> str:
        """Convert lowercase video_id to mixed-case filename format
        Example: '01_7l_departure_north' -> '01_7L_Departure_North'
        """
        parts = video_id.split("_")
        formatted_parts = []

        for i, part in enumerate(parts):
            # Keep the first part (number) as-is
            if i == 0 and part.isdigit():
                formatted_parts.append(part)
            # Handle runway designators like "7l", "7r" -> "7L", "7R"
            elif part.lower() in ["7l", "7r", "25l", "25r", "25c"] or (
                len(part) == 2
                and part[0].isdigit()
                and part[1].lower() in ["l", "r", "c"]
            ):
                formatted_parts.append(part.upper())
            # Handle common aviation abbreviations
            elif part.upper() in {
                "VFR",
                "IFR",
                "GPS",
                "VOR",
                "ILS",
                "DME",
                "ATC",
                "FSS",
                "CTAF",
                "UNICOM",
                "ATIS",
            }:
                formatted_parts.append(part.upper())
            # Handle special cases like "st" in "st_augustine"
            elif part.lower() == "st":
                formatted_parts.append("St")
            # Capitalize regular words
            else:
                formatted_parts.append(part.capitalize())

        return "_".join(formatted_parts)

    @staticmethod
    async def get_videos_for_student(student_id: str) -> List[Dict[str, Any]]:
        """Get all videos with progress information for a student"""
        videos_with_progress = await DatabaseManager.get_student_video_progress(
            student_id
        )

        # Preload ground truth for the student's videos and build scoring summary
        ground_truth_cache: Dict[str, List[str]] = {}
        for video in videos_with_progress:
            messages = await VideoService.get_video_ground_truth(video["id"])
            ground_truth_cache[video["id"]] = messages or []

        def fetch_ground_truth(video_id: str) -> List[str]:
            return ground_truth_cache.get(video_id, [])

        asr_results = await DatabaseManager.get_student_asr_results(student_id)
        score_summary = summarize_scores_by_video(asr_results, fetch_ground_truth)

        result = []
        for video in videos_with_progress:
            # Convert None values to appropriate defaults
            time_spent_seconds = int(video.get("time_spent_seconds") or 0)
            time_spent_minutes = (
                round(time_spent_seconds / 60, 1) if time_spent_seconds > 0 else 0
            )
            summary = score_summary.get(video["id"])
            if summary:
                avg_score = float(summary.get("average", 0.0))
                matched_messages = len(summary.get("message_scores", {}))
            else:
                avg_score = float(video.get("best_score") or 0.0)
                matched_messages = 0

            # Always unlock the first video (order_index = 1)
            is_unlocked = bool(video.get("unlocked") or False)
            if video["order_index"] == 1:
                is_unlocked = True

            result.append(
                {
                    "id": video["id"],
                    "title": video["title"],
                    "description": video["description"],
                    "filename": video["filename"],
                    "order_index": video["order_index"],
                    "duration": video["duration"],
                    "unlocked": is_unlocked,
                    "completed": bool(video.get("completed") or False),
                    "best_score": avg_score,
                    "average_score": avg_score,
                    "matched_messages": matched_messages,
                    "attempts": int(video.get("attempts") or 0),
                    "last_attempt": video.get("last_attempt"),
                    "time_spent_seconds": time_spent_seconds,
                    "time_spent_minutes": time_spent_minutes,
                    "video_url": f"/videos/{video['filename']}",
                }
            )

        return result

    @staticmethod
    async def get_video_ground_truth(video_id: str) -> Optional[List[str]]:
        """Get ground truth text for a video as a list of messages"""
        ground_truth_dir = Path(__file__).parent.parent.parent / "data" / "ground_truth"

        # Generate mixed-case version for new naming convention
        # Convert from "01_7l_departure_north" to "01_7L_Departure_North"
        mixed_case_id = VideoService._convert_to_mixed_case(video_id)

        # Try different possible filenames
        possible_files = [
            ground_truth_dir / f"{video_id}.txt",  # Lowercase (old format)
            ground_truth_dir / f"{mixed_case_id}.txt",  # Mixed case (new format)
            ground_truth_dir / f"{video_id}_ground_truth.txt",
            ground_truth_dir / f"ground_truth_{video_id}.txt",
        ]

        for file_path in possible_files:
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if not content:
                            return None
                        # Split by "---" delimiter to get individual messages
                        messages = [
                            msg.strip() for msg in content.split("---") if msg.strip()
                        ]
                        return messages if messages else None
                except Exception as e:
                    print(f"⚠️  Error reading ground truth file {file_path}: {e}")

        return None

    @staticmethod
    async def set_video_ground_truth(video_id: str, ground_truth: str) -> bool:
        """Set ground truth text for a video"""
        ground_truth_dir = Path(__file__).parent.parent.parent / "data" / "ground_truth"
        ground_truth_dir.mkdir(parents=True, exist_ok=True)

        file_path = ground_truth_dir / f"{video_id}.txt"

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(ground_truth.strip())

            # Update database
            async with await DatabaseManager.get_connection() as db:
                await db.execute(
                    """
                    UPDATE videos SET ground_truth_file = ? WHERE id = ?
                """,
                    (str(file_path), video_id),
                )
                await db.commit()

            print(f"📝 Set ground truth for video {video_id}")
            return True

        except Exception as e:
            print(f"❌ Error setting ground truth for video {video_id}: {e}")
            return False

    @staticmethod
    async def check_video_access(student_id: str, video_id: str) -> bool:
        """Check if student has access to a specific video"""
        async with await DatabaseManager.get_connection() as db:
            async with db.execute(
                """
                SELECT unlocked FROM video_progress 
                WHERE student_id = ? AND video_id = ?
            """,
                (student_id, video_id),
            ) as cursor:
                result = await cursor.fetchone()

                if result:
                    return bool(result[0])

                # If no record exists, check if this is the first video
                async with db.execute(
                    """
                    SELECT order_index FROM videos WHERE id = ?
                """,
                    (video_id,),
                ) as cursor:
                    video_result = await cursor.fetchone()
                    if video_result and video_result[0] == 1:
                        # First video should be accessible, create the record
                        await db.execute(
                            """
                            INSERT OR REPLACE INTO video_progress (student_id, video_id, unlocked)
                            VALUES (?, ?, TRUE)
                        """,
                            (student_id, video_id),
                        )
                        await db.commit()
                        return True

                return False

    @staticmethod
    def get_video_file_path(filename: str) -> Optional[Path]:
        """Get the full path to a video file"""
        videos_dir = Path(__file__).parent.parent.parent / "videos"
        video_path = videos_dir / filename

        return video_path if video_path.exists() else None
