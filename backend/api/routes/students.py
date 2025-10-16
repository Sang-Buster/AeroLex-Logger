#!/usr/bin/env python3
"""
Students API Routes
Handles student data, progress tracking, and statistics
"""

from typing import Optional

from database.sqlite_db import DatabaseManager
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from services.student_service import StudentService

router = APIRouter()


class ProgressUpdate(BaseModel):
    video_id: str
    completed: bool = False
    score: float = 0.0


@router.get("/{student_id}/progress")
async def get_student_progress(student_id: str):
    """Get comprehensive student progress data"""
    try:
        progress_data = await StudentService.get_student_progress(student_id)
        return {"success": True, "data": progress_data}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"❌ Error getting student progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get student progress",
        )


@router.post("/{student_id}/progress")
async def update_student_progress(student_id: str, progress: ProgressUpdate):
    """Update student progress on a video"""
    try:
        await StudentService.update_video_progress(
            student_id=student_id,
            video_id=progress.video_id,
            completed=progress.completed,
            score=progress.score,
        )

        return {"success": True, "message": "Progress updated successfully"}

    except Exception as e:
        print(f"❌ Error updating progress: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update progress",
        )


@router.get("/{student_id}/statistics")
async def get_student_statistics(student_id: str):
    """Get detailed student statistics"""
    try:
        progress_data = await StudentService.get_student_progress(student_id)

        # Additional statistics
        asr_results = await DatabaseManager.get_student_asr_results(student_id)

        # Calculate detailed stats
        stats = progress_data["statistics"]

        # WER and CER statistics
        wer_scores = [r["wer"] for r in asr_results if r["wer"] is not None]
        cer_scores = [r["cer"] for r in asr_results if r["cer"] is not None]

        detailed_stats = {
            **stats,
            "average_wer": sum(wer_scores) / len(wer_scores) if wer_scores else 0.0,
            "average_cer": sum(cer_scores) / len(cer_scores) if cer_scores else 0.0,
            "best_wer": min(wer_scores) if wer_scores else 1.0,
            "best_cer": min(cer_scores) if cer_scores else 1.0,
            "transcription_count": len(asr_results),
        }

        return {
            "success": True,
            "statistics": detailed_stats,
            "video_scores": progress_data["video_scores"],
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"❌ Error getting student statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get student statistics",
        )


@router.get("/{student_id}/asr-results")
async def get_student_asr_results(
    student_id: str, video_id: Optional[str] = None, limit: int = 50
):
    """Get ASR results for a student"""
    try:
        asr_results = await DatabaseManager.get_student_asr_results(
            student_id, video_id
        )

        # Limit results
        if limit > 0:
            asr_results = asr_results[:limit]

        return {"success": True, "results": asr_results, "count": len(asr_results)}

    except Exception as e:
        print(f"❌ Error getting ASR results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ASR results",
        )


@router.get("/{student_id}/dashboard")
async def get_student_dashboard(student_id: str):
    """Get dashboard data for student"""
    try:
        progress_data = await StudentService.get_student_progress(student_id)

        # Get recent ASR results
        recent_results = progress_data["recent_results"][:5]  # Last 5 results

        # Format dashboard data
        dashboard_data = {
            "student": progress_data["student"],
            "quick_stats": {
                "completed_videos": progress_data["statistics"]["completed_videos"],
                "total_videos": progress_data["statistics"]["total_videos"],
                "average_score": progress_data["statistics"]["average_score"],
                "total_attempts": progress_data["statistics"]["total_attempts"],
            },
            "recent_activity": [
                {
                    "video_id": result["video_id"],
                    "transcript": result["transcript"][:100] + "..."
                    if len(result["transcript"]) > 100
                    else result["transcript"],
                    "similarity_score": result["similarity_score"],
                    "timestamp": result["timestamp"],
                }
                for result in recent_results
            ],
            "video_progress": [
                {
                    "video_id": video["id"],
                    "title": video["title"],
                    "unlocked": video["unlocked"],
                    "completed": video["completed"],
                    "best_score": video["best_score"],
                }
                for video in progress_data["videos"][:6]  # First 6 videos for dashboard
            ],
        }

        return {"success": True, "dashboard": dashboard_data}

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        print(f"❌ Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard data",
        )
