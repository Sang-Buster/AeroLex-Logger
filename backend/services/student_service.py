#!/usr/bin/env python3
"""
Student Management Service
Handles student registration, authentication, and progress tracking
"""

import uuid
from pathlib import Path
from typing import Any, Dict

from database.sqlite_db import DatabaseManager


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

        # Get ASR results summary
        asr_results = await DatabaseManager.get_student_asr_results(student_id)

        # Calculate statistics
        total_videos = len(video_progress)
        unlocked_videos = len([v for v in video_progress if v.get("unlocked")])
        completed_videos = len([v for v in video_progress if v.get("completed")])

        # Calculate average scores
        scores = [
            r["similarity_score"]
            for r in asr_results
            if r["similarity_score"] is not None
        ]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Get best scores per video
        video_scores = {}
        for result in asr_results:
            video_id = result["video_id"]
            score = result["similarity_score"] or 0.0
            if video_id not in video_scores or score > video_scores[video_id]:
                video_scores[video_id] = score

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
                "total_attempts": len(asr_results),
            },
            "video_scores": video_scores,
            "recent_results": asr_results[:10],  # Last 10 results
        }

    @staticmethod
    async def update_video_progress(
        student_id: str, video_id: str, completed: bool = False, score: float = 0.0
    ):
        """Update student's progress on a specific video"""

        # Update video progress
        async with await DatabaseManager.get_connection() as db:
            # Update or insert video progress
            await db.execute(
                """
                INSERT OR REPLACE INTO video_progress 
                (student_id, video_id, unlocked, completed, best_score, attempts, last_attempt)
                SELECT 
                    ?,
                    ?,
                    COALESCE((SELECT unlocked FROM video_progress WHERE student_id = ? AND video_id = ?), TRUE),
                    ?,
                    MAX(COALESCE((SELECT best_score FROM video_progress WHERE student_id = ? AND video_id = ?), 0), ?),
                    COALESCE((SELECT attempts FROM video_progress WHERE student_id = ? AND video_id = ?), 0) + 1,
                    CURRENT_TIMESTAMP
            """,
                (
                    student_id,
                    video_id,
                    student_id,
                    video_id,
                    completed,
                    student_id,
                    video_id,
                    score,
                    student_id,
                    video_id,
                ),
            )

            await db.commit()

        # If video is completed, unlock next video
        if completed:
            await DatabaseManager.unlock_next_video(student_id, video_id)
            print(
                f"🎯 Student {student_id} completed video {video_id} (score: {score:.3f})"
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
