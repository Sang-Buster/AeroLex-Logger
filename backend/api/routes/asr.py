#!/usr/bin/env python3
"""
ASR API Routes
Handles ASR transcription, evaluation, and integration with student sessions
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

# Add src directory to path for ASR imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from database.sqlite_db import DatabaseManager  #noqa: E402
from services.student_service import StudentService  #noqa: E402
from services.video_service import VideoService  #noqa: E402

router = APIRouter()


class ASRSessionRequest(BaseModel):
    student_id: str
    video_id: str
    session_id: Optional[str] = None


class ASRResultRequest(BaseModel):
    session_id: str
    student_id: str
    video_id: str
    transcript: str
    confidence: float = 0.0
    audio_file_path: Optional[str] = None


class EvaluationRequest(BaseModel):
    student_id: str
    video_id: str
    transcript: str
    ground_truth: Optional[str] = None


@router.post("/start-session")
async def start_asr_session(request: ASRSessionRequest):
    """Start an ASR session for a student watching a video"""
    try:
        # Validate student and video access
        has_access = await VideoService.check_video_access(request.student_id, request.video_id)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this video"
            )
        
        # Start the ASR service for this student
        session_config = {
            "student_id": request.student_id,
            "video_id": request.video_id,
            "session_id": request.session_id,
            "audio_dir": str(await StudentService.get_student_audio_dir(request.student_id)),
            "logs_dir": str(await StudentService.get_student_logs_dir(request.student_id))
        }
        
        # Store session configuration for the ASR service to pick up
        await store_asr_session_config(session_config)
        
        return {
            "success": True,
            "message": "ASR session started",
            "student_id": request.student_id,
            "video_id": request.video_id,
            "session_id": request.session_id,
            "config": session_config
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting ASR session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start ASR session"
        )


@router.post("/submit-result")
async def submit_asr_result(request: ASRResultRequest, background_tasks: BackgroundTasks):
    """Submit an ASR transcription result for evaluation"""
    try:
        # Get ground truth for the video
        ground_truth = await VideoService.get_video_ground_truth(request.video_id)
        
        # Evaluate the transcription if we have ground truth
        evaluation_results = None
        if ground_truth and request.transcript.strip():
            evaluation_results = await evaluate_transcription(
                request.transcript, 
                ground_truth
            )
        
        # Prepare ASR result data
        asr_data = {
            "session_id": request.session_id,
            "student_id": request.student_id,
            "video_id": request.video_id,
            "transcript": request.transcript,
            "ground_truth": ground_truth,
            "confidence": request.confidence,
            "audio_file_path": request.audio_file_path
        }
        
        # Add evaluation results if available
        if evaluation_results:
            asr_data.update({
                "wer": evaluation_results["wer"],
                "cer": evaluation_results["cer"],
                "similarity_score": evaluation_results["similarity"]
            })
        
        # Save to database
        asr_result_id = await DatabaseManager.save_asr_result(asr_data)
        
        # Update student progress if we have a good similarity score
        if evaluation_results and evaluation_results["similarity"] > 0.7:
            background_tasks.add_task(
                StudentService.update_video_progress,
                request.student_id,
                request.video_id,
                True,  # completed
                evaluation_results["similarity"]
            )
        
        response_data = {
            "success": True,
            "asr_result_id": asr_result_id,
            "message": "ASR result processed successfully",
            "transcript": request.transcript,
            "confidence": request.confidence
        }
        
        # Add evaluation results to response
        if evaluation_results:
            response_data["evaluation"] = evaluation_results
        
        return response_data
        
    except Exception as e:
        print(f"❌ Error submitting ASR result: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process ASR result"
        )


@router.post("/evaluate")
async def evaluate_transcript(request: EvaluationRequest):
    """Evaluate a transcript against ground truth"""
    try:
        # Get ground truth if not provided
        ground_truth = request.ground_truth
        if not ground_truth:
            ground_truth = await VideoService.get_video_ground_truth(request.video_id)
        
        if not ground_truth:
            return {
                "success": False,
                "message": "No ground truth available for this video",
                "video_id": request.video_id
            }
        
        # Perform evaluation
        evaluation_results = await evaluate_transcription(request.transcript, ground_truth)
        
        return {
            "success": True,
            "transcript": request.transcript,
            "ground_truth": ground_truth,
            "evaluation": evaluation_results
        }
        
    except Exception as e:
        print(f"❌ Error evaluating transcript: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate transcript"
        )


@router.get("/session/{session_id}/results")
async def get_session_results(session_id: str):
    """Get ASR results for a specific session"""
    try:
        # Validate session_id
        if not session_id or not session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID"
            )
        
        async with await DatabaseManager.get_connection() as db:
            db.row_factory = db.Row
            
            # First check if the table exists
            async with db.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name='asr_results'
            """) as cursor:
                table_exists = await cursor.fetchone()
                
            if not table_exists:
                print("⚠️ ASR results table does not exist")
                return {
                    "success": True,
                    "session_id": session_id,
                    "results": [],
                    "count": 0,
                    "message": "No ASR results table found"
                }
            
            # Query the results
            async with db.execute("""
                SELECT * FROM asr_results WHERE session_id = ? ORDER BY timestamp DESC
            """, (session_id,)) as cursor:
                results = await cursor.fetchall()
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "results": [dict(row) for row in results] if results else [],
                    "count": len(results) if results else 0
                }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting session results: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session results: {str(e)}"
        )


@router.get("/student/{student_id}/live-transcription")
async def get_live_transcription(student_id: str):
    """Get live transcription data for a student (for real-time display)"""
    try:
        # Read the latest transcription from the student's log file
        logs_dir = await StudentService.get_student_logs_dir(student_id)
        asr_log_file = logs_dir / "asr_results.jsonl"        
        if not asr_log_file.exists():
            # Ensure the directory exists
            logs_dir.mkdir(parents=True, exist_ok=True)
            # Create empty log file so the ASR service can write to it
            asr_log_file.touch()
            print(f"📝 Created transcription log file: {asr_log_file}")
            return {
                "success": True,
                "transcriptions": [],
                "message": f"Ready for transcriptions. Log directory: {logs_dir}"
            }
        
        # Read the last few transcriptions
        transcriptions = []
        try:
            with open(asr_log_file, 'r') as f:
                lines = f.readlines()
                # Get last 10 transcriptions
                for line in lines[-10:]:
                    if line.strip():
                        try:
                            transcriptions.append(json.loads(line.strip()))
                        except json.JSONDecodeError as je:
                            print(f"⚠️ Invalid JSON in transcription log: {je}")
                            continue
        except Exception as e:
            print(f"⚠️  Error reading transcription log: {e}")
        
        return {
            "success": True,
            "transcriptions": transcriptions,
            "count": len(transcriptions),
            "log_file": str(asr_log_file)
        }
        
    except Exception as e:
        print(f"❌ Error getting live transcription: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get live transcription: {str(e)}"
        )


@router.get("/student/{student_id}/debug")
async def debug_student_asr_setup(student_id: str):
    """Debug endpoint to check student ASR setup and directories"""
    try:
        from database.sqlite_db import DatabaseManager
        
        # Get student info
        student_data = await DatabaseManager.get_student(student_id)
        if not student_data:
            return {
                "success": False,
                "error": "Student not found",
                "student_id": student_id
            }
        
        # Get directory paths
        logs_dir = await StudentService.get_student_logs_dir(student_id)
        audio_dir = await StudentService.get_student_audio_dir(student_id)
        asr_log_file = logs_dir / "asr_results.jsonl"
        
        # Check file/directory status
        debug_info = {
            "success": True,
            "student_data": {
                "id": student_data['id'],
                "name": student_data['name'], 
                "student_id": student_data['student_id']
            },
            "directories": {
                "logs_dir": str(logs_dir),
                "logs_dir_exists": logs_dir.exists(),
                "audio_dir": str(audio_dir),
                "audio_dir_exists": audio_dir.exists(),
                "asr_log_file": str(asr_log_file),
                "asr_log_file_exists": asr_log_file.exists()
            }
        }
        
        # If log file exists, get some basic info
        if asr_log_file.exists():
            try:
                with open(asr_log_file, 'r') as f:
                    lines = f.readlines()
                    debug_info["log_file_info"] = {
                        "line_count": len(lines),
                        "file_size_bytes": asr_log_file.stat().st_size,
                        "last_lines": [line.strip() for line in lines[-3:] if line.strip()]
                    }
            except Exception as e:
                debug_info["log_file_error"] = str(e)
        
        # Check session config files
        session_config_dir = Path(__file__).parent.parent.parent.parent / "data" / "asr_sessions"
        session_config_file = session_config_dir / f"session_{student_id}.json"
        
        debug_info["session_config"] = {
            "config_dir": str(session_config_dir),
            "config_dir_exists": session_config_dir.exists(),
            "session_file": str(session_config_file),
            "session_file_exists": session_config_file.exists()
        }
        
        if session_config_file.exists():
            try:
                with open(session_config_file, 'r') as f:
                    import json
                    debug_info["session_config"]["content"] = json.load(f)
            except Exception as e:
                debug_info["session_config"]["error"] = str(e)
        
        return debug_info
        
    except Exception as e:
        print(f"❌ Error in debug endpoint: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "student_id": student_id
        }


# Helper functions

async def store_asr_session_config(config: Dict[str, Any]):
    """Store ASR session configuration for the ASR service to pick up"""
    config_dir = Path(__file__).parent.parent.parent.parent / "data" / "asr_sessions"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / f"session_{config['student_id']}.json"
    
    # Add timestamp
    config["created_at"] = datetime.now().isoformat()
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)


async def evaluate_transcription(transcript: str, ground_truth: str) -> Dict[str, Any]:
    """Evaluate a transcription against ground truth using the existing ASR evaluation module"""
    try:
        # Import the evaluation functions
        from asr_evaluate import evaluate_single_pair
        
        # Perform evaluation
        evaluation = evaluate_single_pair(ground_truth, transcript)
        
        return {
            "wer": evaluation["wer"],
            "cer": evaluation["cer"],
            "word_accuracy": evaluation["word_accuracy"],
            "char_accuracy": evaluation["char_accuracy"],
            "similarity": evaluation["similarity"],
            "edit_distance": evaluation["edit_distance"]
        }
        
    except ImportError as e:
        print(f"❌ Error importing ASR evaluation: {e}")
        # Fallback to simple similarity calculation
        from difflib import SequenceMatcher
        
        def normalize_text(text):
            import re
            text = text.lower()
            text = re.sub(r'[^\w\s]', '', text)
            return ' '.join(text.split())
        
        similarity = SequenceMatcher(
            None, 
            normalize_text(ground_truth), 
            normalize_text(transcript)
        ).ratio()
        
        return {
            "wer": 1.0 - similarity,  # Approximation
            "cer": 1.0 - similarity,  # Approximation
            "word_accuracy": similarity,
            "char_accuracy": similarity,
            "similarity": similarity,
            "edit_distance": 0  # Not calculated in fallback
        }
        
    except Exception as e:
        print(f"❌ Error in transcript evaluation: {e}")
        return {
            "wer": 1.0,
            "cer": 1.0,
            "word_accuracy": 0.0,
            "char_accuracy": 0.0,
            "similarity": 0.0,
            "edit_distance": len(transcript)
        }
