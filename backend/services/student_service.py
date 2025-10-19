#!/usr/bin/env python3
"""
Student Management Service
Handles student registration, authentication, and progress tracking
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List

from database.sqlite_db import DatabaseManager
from services.evaluation_service import summarize_scores_by_video
from services.video_service import VideoService


class StudentService:
    """Service for managing students and their progress"""

    @staticmethod
    def create_student_directories(name: str, student_id: str):
        """Create directories for student data storage"""
        base_dir = Path(__file__).parent.parent.parent

        # Create folder name in format: studentname_studentid
        folder_name = f"{name.replace(' ', '_')}_{student_id}"

        directories = [
            base_dir / "audios" / "students" / folder_name,
            base_dir / "logs" / "students" / folder_name,
            base_dir / "backend" / "static" / "students" / folder_name,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created student directory: {directory}")

        return directories

    @staticmethod
    def generate_student_uuid(name: str, student_id: str) -> str:
        """Generate a unique UUID for the student"""
        # Create a deterministic UUID based on name and student_id
        seed = f"{name.lower().strip()}:{student_id.strip()}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))

    @staticmethod
    async def register_student(name: str, student_id: str) -> Dict[str, Any]:
        """Register a new student or return existing one"""

        # Validate input
        if not name.strip() or not student_id.strip():
            raise ValueError("Name and Student ID are required")

        # Check if student already exists
        existing_student = await DatabaseManager.get_student(student_id)
        if existing_student:
            # Update last active and return existing student
            await DatabaseManager.update_student_activity(student_id)
            print(f"👋 Welcome back, {existing_student['name']} (ID: {student_id})")
            return {
                "id": existing_student["id"],
                "name": existing_student["name"],
                "student_id": existing_student["student_id"],
                "is_new": False,
                "message": "Welcome back!",
            }

        # Create new student
        student_uuid = StudentService.generate_student_uuid(name, student_id)

        student_data = {
            "id": student_uuid,
            "name": name.strip(),
            "student_id": student_id.strip(),
        }

        try:
            # Create student in database
            await DatabaseManager.create_student(student_data)

            # Create student directories
            StudentService.create_student_directories(name.strip(), student_id)

            print(f"🆕 New student registered: {name} (ID: {student_id})")

            return {
                **student_data,
                "is_new": True,
                "message": "Welcome to VR Flight Training!",
            }

        except ValueError as e:
            raise e
        except Exception as e:
            raise Exception(f"Failed to register student: {str(e)}")

    @staticmethod
    async def get_student_progress(student_id: str) -> Dict[str, Any]:
        """Get comprehensive student progress data"""

        # Get student info
        student = await DatabaseManager.get_student(student_id)
        if not student:
            raise ValueError("Student not found")

        # Get video progress
        video_progress = await DatabaseManager.get_student_video_progress(student_id)

        # Preload ground truth messages for scoring calculations
        ground_truth_cache: Dict[str, List[str]] = {}
        for video in video_progress:
            messages = await VideoService.get_video_ground_truth(video["id"])
            ground_truth_cache[video["id"]] = messages or []

        def fetch_ground_truth(video_id: str) -> List[str]:
            return ground_truth_cache.get(video_id, [])

        # Get ASR results summary
        asr_results = await DatabaseManager.get_student_asr_results(student_id)
        score_summary = summarize_scores_by_video(asr_results, fetch_ground_truth)

        # Get total time spent from sessions
        total_time_seconds = 0
        async with await DatabaseManager.get_connection() as db:
            async with db.execute(
                """
                SELECT SUM(duration) as total_duration
                FROM student_sessions
                WHERE student_id = ? AND status = 'completed' AND duration IS NOT NULL
            """,
                (student_id,),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    total_time_seconds = row[0]

        # Calculate statistics
        total_videos = len(video_progress)
        unlocked_videos = len([v for v in video_progress if v.get("unlocked")])
        completed_videos = len([v for v in video_progress if v.get("completed")])

        watched_video_scores = []
        for video in video_progress:
            video_id = video["id"]
            summary = score_summary.get(video_id)
            if summary:
                message_scores = summary.get("message_scores", {})
                average_score = float(summary.get("average", 0.0))
            else:
                message_scores = {}
                average_score = float(video.get("best_score") or 0.0)

            video["average_score"] = average_score
            video["matched_messages"] = len(message_scores)
            # Maintain backward compatibility with existing UI badges
            video["best_score"] = average_score

            if (video.get("attempts") or 0) > 0:
                watched_video_scores.append(average_score)

        avg_score = (
            sum(watched_video_scores) / len(watched_video_scores)
            if watched_video_scores
            else 0.0
        )

        video_scores = {
            video["id"]: video.get("average_score", 0.0) for video in video_progress
        }

        total_attempts = sum(
            int(video.get("attempts") or 0) for video in video_progress
        )

        return {
            "student": student,
            "videos": video_progress,
            "statistics": {
                "total_videos": total_videos,
                "unlocked_videos": unlocked_videos,
                "completed_videos": completed_videos,
                "completion_rate": completed_videos / total_videos
                if total_videos > 0
                else 0,
                "average_score": round(avg_score, 3),
                "total_attempts": total_attempts,
                "total_time_seconds": total_time_seconds,
                "total_time_minutes": round(total_time_seconds / 60, 1),
            },
            "video_scores": video_scores,
            "recent_results": asr_results[:10],  # Last 10 results
        }

    @staticmethod
    async def update_video_progress(
        student_id: str,
        video_id: str,
        completed: bool = False,
        score: float = 0.0,
        matched_ground_truth: str = "",
    ):
        """Update student's progress on a specific video

        Only increments attempts when practicing a NEW unique ground truth message.
        """

        # Update video progress
        async with await DatabaseManager.get_connection() as db:
            # Get current progress
            async with db.execute(
                """
                SELECT unlocked, completed, best_score, attempts 
                FROM video_progress 
                WHERE student_id = ? AND video_id = ?
            """,
                (student_id, video_id),
            ) as cursor:
                current_progress = await cursor.fetchone()

            # Get the last matched ground truth for this student and video
            async with db.execute(
                """
                SELECT ground_truth 
                FROM asr_results 
                WHERE student_id = ? AND video_id = ?
                ORDER BY timestamp DESC 
                LIMIT 2
            """,
                (student_id, video_id),
            ) as cursor:
                recent_results = await cursor.fetchall()

            # Determine if this is a new unique attempt
            # Only increment if the matched_ground_truth is different from the most recent one
            should_increment_attempt = False

            if matched_ground_truth:
                # If we have at least 2 results, compare current with previous
                if len(recent_results) >= 2:
                    # recent_results[0] is the CURRENT submission (just saved)
                    # recent_results[1] is the PREVIOUS submission
                    previous_ground_truth = (
                        recent_results[1][0] if recent_results[1] else ""
                    )

                    # Only increment if practicing a different message
                    if matched_ground_truth != previous_ground_truth:
                        should_increment_attempt = True
                else:
                    # First or second attempt - always count
                    should_increment_attempt = True

            if current_progress:
                # Update existing progress
                (
                    current_unlocked,
                    current_completed,
                    current_best_score,
                    current_attempts,
                ) = current_progress

                # Update best score (keep highest) - only update if score > 0
                if score > 0:
                    new_best_score = max(current_best_score or 0.0, score)
                else:
                    new_best_score = current_best_score or 0.0

                # Mark as completed if score is good OR already completed
                new_completed = completed or current_completed

                # Increment attempts ONLY if practicing a new unique message
                if should_increment_attempt:
                    new_attempts = (current_attempts or 0) + 1
                else:
                    new_attempts = current_attempts or 0

                await db.execute(
                    """
                    UPDATE video_progress 
                    SET completed = ?, best_score = ?, attempts = ?, last_attempt = CURRENT_TIMESTAMP
                    WHERE student_id = ? AND video_id = ?
                """,
                    (new_completed, new_best_score, new_attempts, student_id, video_id),
                )
            else:
                # Insert new progress (first attempt)
                await db.execute(
                    """
                    INSERT INTO video_progress 
                    (student_id, video_id, unlocked, completed, best_score, attempts, last_attempt)
                    VALUES (?, ?, TRUE, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                    (student_id, video_id, completed, score),
                )

            await db.commit()

        # Check time spent and unlock next video if sufficient time has been spent
        await StudentService.check_time_based_unlock(student_id, video_id, score)

    @staticmethod
    async def get_video_time_spent(student_id: str, video_id: str) -> int:
        """Get total time spent by student on a specific video"""
        async with await DatabaseManager.get_connection() as db:
            async with db.execute(
                """
                SELECT COALESCE(SUM(duration), 0) as total_time
                FROM student_sessions
                WHERE student_id = ? AND video_id = ? AND status = 'completed' AND duration IS NOT NULL
            """,
                (student_id, video_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    @staticmethod
    async def check_time_based_unlock(
        student_id: str, video_id: str, score: float = 0.0
    ):
        """Unlock the next video once engagement threshold is met."""
        time_spent = await StudentService.get_video_time_spent(student_id, video_id)

        if time_spent >= 10:
            print(
                f"✅ Student spent {time_spent}s on video {video_id} - unlocking next video..."
            )
            await DatabaseManager.unlock_next_video(student_id, video_id)
            print(
                f"🔓 Next video unlocked for student {student_id} after {time_spent}s engagement"
            )
        else:
            print(
                f"📊 Video {video_id} progress updated (attempts incremented, score: {score:.3f}, time: {time_spent}s)"
            )

    @staticmethod
    async def migrate_student_directories(student_id: str):
        """Migrate existing student from old directory format to new format"""
        from database.sqlite_db import DatabaseManager

        # Get student info from database
        student_data = await DatabaseManager.get_student(student_id)
        if not student_data:
            return False

        base_dir = Path(__file__).parent.parent.parent
        old_audio_dir = base_dir / "audios" / student_id
        old_logs_dir = base_dir / "logs" / "students" / student_id

        # Create new format directory name
        folder_name = f"{student_data['name'].replace(' ', '_')}_{student_id}"
        new_audio_dir = base_dir / "audios" / "students" / folder_name
        new_logs_dir = base_dir / "logs" / "students" / folder_name

        # Migrate directories if old format exists
        migrated = False
        try:
            if old_audio_dir.exists() and not new_audio_dir.exists():
                new_audio_dir.parent.mkdir(parents=True, exist_ok=True)
                old_audio_dir.rename(new_audio_dir)
                print(f"📁 Migrated audio directory: {old_audio_dir} → {new_audio_dir}")
                migrated = True

            if old_logs_dir.exists() and not new_logs_dir.exists():
                new_logs_dir.parent.mkdir(parents=True, exist_ok=True)
                old_logs_dir.rename(new_logs_dir)
                print(f"📁 Migrated logs directory: {old_logs_dir} → {new_logs_dir}")
                migrated = True

        except Exception as e:
            print(f"⚠️ Error migrating directories for student {student_id}: {e}")

        return migrated

    @staticmethod
    async def get_student_audio_dir(student_id: str) -> Path:
        """Get student's audio directory path"""
        base_dir = Path(__file__).parent.parent.parent

        # First try to find existing directory with name_id format
        audios_dir = base_dir / "audios" / "students"
        if audios_dir.exists():
            for dir_path in audios_dir.iterdir():
                if dir_path.is_dir() and dir_path.name.endswith(f"_{student_id}"):
                    return dir_path

        # Check if old format exists and migrate
        old_dir = base_dir / "audios" / student_id
        if old_dir.exists():
            await StudentService.migrate_student_directories(student_id)
            # Try again after migration
            if audios_dir.exists():
                for dir_path in audios_dir.iterdir():
                    if dir_path.is_dir() and dir_path.name.endswith(f"_{student_id}"):
                        return dir_path

        # Fallback - create new format directory
        from database.sqlite_db import DatabaseManager

        student_data = await DatabaseManager.get_student(student_id)
        if student_data:
            folder_name = f"{student_data['name'].replace(' ', '_')}_{student_id}"
            new_dir = base_dir / "audios" / "students" / folder_name
            new_dir.mkdir(parents=True, exist_ok=True)
            return new_dir

        # Last resort - old format for backward compatibility
        return base_dir / "audios" / "students" / student_id

    @staticmethod
    async def get_student_logs_dir(student_id: str) -> Path:
        """Get student's logs directory path"""
        base_dir = Path(__file__).parent.parent.parent

        # First try to find existing directory with name_id format
        logs_dir = base_dir / "logs" / "students"
        if logs_dir.exists():
            for dir_path in logs_dir.iterdir():
                if dir_path.is_dir() and dir_path.name.endswith(f"_{student_id}"):
                    return dir_path

        # Check if old format exists and migrate
        old_dir = base_dir / "logs" / "students" / student_id
        if old_dir.exists():
            await StudentService.migrate_student_directories(student_id)
            # Try again after migration
            if logs_dir.exists():
                for dir_path in logs_dir.iterdir():
                    if dir_path.is_dir() and dir_path.name.endswith(f"_{student_id}"):
                        return dir_path

        # Fallback - create new format directory
        from database.sqlite_db import DatabaseManager

        student_data = await DatabaseManager.get_student(student_id)
        if student_data:
            folder_name = f"{student_data['name'].replace(' ', '_')}_{student_id}"
            new_dir = base_dir / "logs" / "students" / folder_name
            new_dir.mkdir(parents=True, exist_ok=True)
            return new_dir

        # Last resort - old format for backward compatibility
        return base_dir / "logs" / "students" / student_id
