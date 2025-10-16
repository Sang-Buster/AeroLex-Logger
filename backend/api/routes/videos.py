#!/usr/bin/env python3
"""
Videos API Routes
Handles video access, metadata, and ground truth management
"""

from typing import Optional

import aiosqlite
from database.sqlite_db import DatabaseManager
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from services.video_service import VideoService

router = APIRouter()


class GroundTruthUpdate(BaseModel):
    ground_truth: str


@router.get("/")
async def get_videos():
    """Get all videos (admin view)"""
    try:
        videos = await DatabaseManager.get_videos()
        return {"success": True, "videos": videos}

    except Exception as e:
        print(f"❌ Error getting videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get videos",
        )


@router.get("/student/{student_id}")
async def get_videos_for_student(student_id: str):
    """Get videos with progress for a specific student"""
    try:
        videos = await VideoService.get_videos_for_student(student_id)

        return {"success": True, "videos": videos, "count": len(videos)}

    except Exception as e:
        print(f"❌ Error getting videos for student: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get videos for student",
        )


@router.get("/{video_id}/access/{student_id}")
async def check_video_access(video_id: str, student_id: str):
    """Check if student has access to a video"""
    try:
        has_access = await VideoService.check_video_access(student_id, video_id)

        return {
            "success": True,
            "has_access": has_access,
            "video_id": video_id,
            "student_id": student_id,
        }

    except Exception as e:
        print(f"❌ Error checking video access: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check video access",
        )


@router.get("/{video_id}/ground-truth")
async def get_video_ground_truth(video_id: str):
    """Get ground truth text for a video"""
    try:
        ground_truth = await VideoService.get_video_ground_truth(video_id)

        return {
            "success": True,
            "video_id": video_id,
            "ground_truth": ground_truth,
            "has_ground_truth": ground_truth is not None,
        }

    except Exception as e:
        print(f"❌ Error getting ground truth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ground truth",
        )


@router.post("/{video_id}/ground-truth")
async def set_video_ground_truth(video_id: str, data: GroundTruthUpdate):
    """Set ground truth text for a video"""
    try:
        success = await VideoService.set_video_ground_truth(video_id, data.ground_truth)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save ground truth",
            )

        return {
            "success": True,
            "message": f"Ground truth updated for video {video_id}",
            "video_id": video_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error setting ground truth: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set ground truth",
        )


@router.get("/{video_id}/metadata")
async def get_video_metadata(video_id: str):
    """Get detailed video metadata"""
    try:
        async with await DatabaseManager.get_connection() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM videos WHERE id = ?", (video_id,)
            ) as cursor:
                video = await cursor.fetchone()

                if not video:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND, detail="Video not found"
                    )

                video_data = dict(video)

                # Get ground truth
                ground_truth = await VideoService.get_video_ground_truth(video_id)
                video_data["ground_truth"] = ground_truth
                video_data["has_ground_truth"] = ground_truth is not None

                # Get video file path and check if exists
                video_file_path = VideoService.get_video_file_path(
                    video_data["filename"]
                )
                video_data["file_exists"] = video_file_path is not None
                video_data["video_url"] = (
                    f"/videos/{video_data['filename']}" if video_file_path else None
                )

                return {"success": True, "video": video_data}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting video metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get video metadata",
        )


@router.post("/{video_id}/start-session/{student_id}")
async def start_video_session(video_id: str, student_id: str):
    """Start a video session for a student"""
    try:
        # Check video access
        has_access = await VideoService.check_video_access(student_id, video_id)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this video",
            )

        # Create session
        import uuid

        session_id = str(uuid.uuid4())

        session_data = {
            "id": session_id,
            "student_id": student_id,
            "video_id": video_id,
            "status": "started",
        }

        await DatabaseManager.create_session(session_data)

        return {
            "success": True,
            "session_id": session_id,
            "video_id": video_id,
            "student_id": student_id,
            "message": "Video session started",
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting video session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start video session",
        )


@router.post("/{session_id}/complete")
async def complete_video_session(session_id: str, duration: Optional[int] = None):
    """Complete a video session"""
    try:
        await DatabaseManager.complete_session(session_id, duration or 0)

        return {
            "success": True,
            "session_id": session_id,
            "message": "Video session completed",
        }

    except Exception as e:
        print(f"❌ Error completing video session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete video session",
        )


@router.post("/initialize")
async def initialize_video_database():
    """Initialize/refresh video database from video files (admin endpoint)"""
    try:
        await VideoService.initialize_videos()

        return {"success": True, "message": "Video database initialized successfully"}

    except Exception as e:
        print(f"❌ Error initializing videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize video database",
        )
