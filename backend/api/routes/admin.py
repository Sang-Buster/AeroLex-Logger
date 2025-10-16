#!/usr/bin/env python3
"""
Admin API Routes
Administrative functionality for VR training application
"""

from typing import List, Optional

import aiosqlite
from database.sqlite_db import DatabaseManager
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


class AdminStudentData(BaseModel):
    """Model for admin student data"""

    id: str
    name: str
    student_id: str
    created_at: str
    last_active: str
    total_videos: int
    completed_videos: int
    completion_rate: float
    average_score: float
    total_attempts: int
    time_spent_minutes: Optional[int] = 0
    latest_activity: Optional[str] = None
    audio_files: List[str] = []


class AdminOverviewData(BaseModel):
    """Model for admin overview statistics"""

    total_students: int
    active_students: int
    class_average: float
    average_completion_rate: float
    average_score: float
    total_audio_files: int


def check_admin_auth(student_id: str):
    """Simple admin auth check"""
    if student_id != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )


@router.get("/overview", response_model=AdminOverviewData)
async def get_admin_overview(admin_id: str):
    """Get admin overview statistics"""
    check_admin_auth(admin_id)

    try:
        async with await DatabaseManager.get_connection() as db:
            db.row_factory = aiosqlite.Row

            # Get total students
            async with db.execute("SELECT COUNT(*) as count FROM students") as cursor:
                row = await cursor.fetchone()
                total_students = row["count"] if row else 0

            # Get active students (last 2 hours - more realistic for current sessions)
            async with db.execute("""
                SELECT COUNT(*) as count FROM students 
                WHERE last_active >= datetime('now', '-2 hours')
            """) as cursor:
                row = await cursor.fetchone()
                active_students = row["count"] if row else 0

            # Get class average score
            async with db.execute("""
                SELECT AVG(similarity_score) * 100 as class_avg 
                FROM asr_results WHERE similarity_score IS NOT NULL
            """) as cursor:
                row = await cursor.fetchone()
                class_average = round(row["class_avg"] or 0, 1)

            # Get average completion rate
            async with db.execute("""
                SELECT AVG(CAST(completed_videos AS FLOAT) / NULLIF(total_videos, 0) * 100) as avg_completion
                FROM students WHERE total_videos > 0
            """) as cursor:
                row = await cursor.fetchone()
                avg_completion_rate = round(row["avg_completion"] or 0, 2)

            # Get average score
            async with db.execute("""
                SELECT AVG(similarity_score) as avg_score 
                FROM asr_results WHERE similarity_score IS NOT NULL
            """) as cursor:
                row = await cursor.fetchone()
                avg_score = round((row["avg_score"] or 0) * 100, 2)

            return AdminOverviewData(
                total_students=total_students,
                active_students=active_students,
                class_average=class_average,
                average_completion_rate=avg_completion_rate,
                average_score=avg_score,
                total_audio_files=0,  # Will be calculated below
            )

    except Exception as e:
        print(f"❌ Admin overview error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch admin overview",
        )


@router.get("/students", response_model=List[AdminStudentData])
async def get_all_students_data(admin_id: str):
    """Get comprehensive data for all students"""
    check_admin_auth(admin_id)

    try:
        async with await DatabaseManager.get_connection() as db:
            db.row_factory = aiosqlite.Row

            students_data = []

            # Get all students with their basic info
            async with db.execute("""
                SELECT * FROM students ORDER BY created_at DESC
            """) as cursor:
                students = await cursor.fetchall()

            for student in students:
                student_dict = dict(student)
                student_id = student_dict["student_id"]

                # Get video progress stats
                async with db.execute(
                    """
                    SELECT 
                        COUNT(*) as total_videos,
                        SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_videos,
                        AVG(best_score) as avg_score,
                        SUM(attempts) as total_attempts
                    FROM video_progress WHERE student_id = ?
                """,
                    (student_id,),
                ) as cursor:
                    progress_row = await cursor.fetchone()
                    progress = dict(progress_row) if progress_row else {}

                # Get session duration
                async with db.execute(
                    """
                    SELECT SUM(duration) as total_duration 
                    FROM student_sessions 
                    WHERE student_id = ? AND duration IS NOT NULL
                """,
                    (student_id,),
                ) as cursor:
                    duration_row = await cursor.fetchone()
                    total_duration = (
                        duration_row["total_duration"] if duration_row else 0
                    )

                # Get latest activity
                async with db.execute(
                    """
                    SELECT timestamp FROM asr_results 
                    WHERE student_id = ? 
                    ORDER BY timestamp DESC LIMIT 1
                """,
                    (student_id,),
                ) as cursor:
                    activity_row = await cursor.fetchone()
                    latest_activity = (
                        activity_row["timestamp"] if activity_row else None
                    )

                # Get audio files
                audio_files = []
                try:
                    from services.student_service import StudentService

                    audio_dir = await StudentService.get_student_audio_dir(student_id)
                    if audio_dir.exists():
                        audio_files = [f.name for f in audio_dir.glob("*.wav")]
                except Exception as e:
                    print(f"⚠️ Could not get audio files for {student_id}: {e}")

                # Calculate completion rate
                total_videos = progress.get("total_videos", 0)
                completed_videos = progress.get("completed_videos", 0)
                completion_rate = (
                    (completed_videos / total_videos * 100) if total_videos > 0 else 0
                )

                # Calculate average score as percentage
                avg_score = (progress.get("avg_score", 0) or 0) * 100

                students_data.append(
                    AdminStudentData(
                        id=student_dict["id"],
                        name=student_dict["name"],
                        student_id=student_dict["student_id"],
                        created_at=student_dict["created_at"],
                        last_active=student_dict["last_active"],
                        total_videos=total_videos,
                        completed_videos=completed_videos,
                        completion_rate=round(completion_rate, 2),
                        average_score=round(avg_score, 2),
                        total_attempts=progress.get("total_attempts", 0) or 0,
                        time_spent_minutes=int((total_duration or 0) / 60),
                        latest_activity=latest_activity,
                        audio_files=audio_files,
                    )
                )

            return students_data

    except Exception as e:
        print(f"❌ Admin students data error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch students data",
        )


@router.get("/student/{student_id}/details")
async def get_student_details(student_id: str, admin_id: str):
    """Get detailed information for a specific student"""
    check_admin_auth(admin_id)

    try:
        async with await DatabaseManager.get_connection() as db:
            db.row_factory = aiosqlite.Row

            # Get student basic info
            student = await DatabaseManager.get_student(student_id)
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")

            # Get ASR results
            async with db.execute(
                """
                SELECT 
                    ar.*, v.title as video_title
                FROM asr_results ar
                LEFT JOIN videos v ON ar.video_id = v.id
                WHERE ar.student_id = ?
                ORDER BY ar.timestamp DESC
            """,
                (student_id,),
            ) as cursor:
                asr_results = [dict(row) for row in await cursor.fetchall()]

            # Get session history
            async with db.execute(
                """
                SELECT 
                    ss.*, v.title as video_title
                FROM student_sessions ss
                LEFT JOIN videos v ON ss.video_id = v.id
                WHERE ss.student_id = ?
                ORDER BY ss.started_at DESC
            """,
                (student_id,),
            ) as cursor:
                sessions = [dict(row) for row in await cursor.fetchall()]

            # Get video progress
            async with db.execute(
                """
                SELECT 
                    vp.*, v.title as video_title
                FROM video_progress vp
                LEFT JOIN videos v ON vp.video_id = v.id
                WHERE vp.student_id = ?
                ORDER BY v.order_index
            """,
                (student_id,),
            ) as cursor:
                video_progress = [dict(row) for row in await cursor.fetchall()]

            return {
                "student": student,
                "asr_results": asr_results,
                "sessions": sessions,
                "video_progress": video_progress,
            }

    except Exception as e:
        print(f"❌ Admin student details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch student details",
        )


@router.get("/student/{student_id}/audio/{audio_filename}")
async def get_student_audio(student_id: str, audio_filename: str, admin_id: str):
    """Serve student audio files for admin playback"""
    check_admin_auth(admin_id)

    try:
        from services.student_service import StudentService

        audio_dir = await StudentService.get_student_audio_dir(student_id)
        audio_path = audio_dir / audio_filename

        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")

        return FileResponse(
            path=audio_path, media_type="audio/wav", filename=audio_filename
        )

    except Exception as e:
        print(f"❌ Admin audio file error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve audio file",
        )


@router.delete("/student/{student_id}")
async def delete_student(student_id: str, admin_id: str):
    """Delete a student and all their data"""
    check_admin_auth(admin_id)

    try:
        async with await DatabaseManager.get_connection() as db:
            # Delete in order to respect foreign key constraints
            await db.execute(
                "DELETE FROM asr_results WHERE student_id = ?", (student_id,)
            )
            await db.execute(
                "DELETE FROM student_sessions WHERE student_id = ?", (student_id,)
            )
            await db.execute(
                "DELETE FROM video_progress WHERE student_id = ?", (student_id,)
            )
            await db.execute("DELETE FROM students WHERE student_id = ?", (student_id,))

            await db.commit()

            return {
                "success": True,
                "message": f"Student {student_id} deleted successfully",
            }

    except Exception as e:
        print(f"❌ Admin delete student error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete student",
        )
