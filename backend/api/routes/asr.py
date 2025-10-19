#!/usr/bin/env python3
"""
ASR API Routes
Handles ASR transcription, evaluation, and integration with student sessions
Includes circular buffer support for Control+Backtick recording
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

# Add src directory to path for ASR imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from database.sqlite_db import DatabaseManager  # noqa: E402
from services.student_service import StudentService  # noqa: E402
from services.video_service import VideoService  # noqa: E402

router = APIRouter()

# Track running ASR processes (for circular buffer recording)
_asr_processes = {}


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
        has_access = await VideoService.check_video_access(
            request.student_id, request.video_id
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this video",
            )

        # Start the ASR service for this student
        session_config = {
            "student_id": request.student_id,
            "video_id": request.video_id,
            "session_id": request.session_id,
            "audio_dir": str(
                await StudentService.get_student_audio_dir(request.student_id)
            ),
            "logs_dir": str(
                await StudentService.get_student_logs_dir(request.student_id)
            ),
        }

        # Store session configuration for the ASR service to pick up
        await store_asr_session_config(session_config)

        return {
            "success": True,
            "message": "ASR session started",
            "student_id": request.student_id,
            "video_id": request.video_id,
            "session_id": request.session_id,
            "config": session_config,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting ASR session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start ASR session",
        )


@router.post("/submit-result")
async def submit_asr_result(
    request: ASRResultRequest, background_tasks: BackgroundTasks
):
    """Submit an ASR transcription result for evaluation"""
    try:
        # Get ground truth messages for the video
        ground_truth_messages = await VideoService.get_video_ground_truth(
            request.video_id
        )

        # Evaluate the transcription if we have ground truth
        evaluation_results = None
        ground_truth_text = None

        if ground_truth_messages and request.transcript.strip():
            evaluation_results = await evaluate_transcription(
                request.transcript, ground_truth_messages
            )
            # Join messages for storage (legacy compatibility)
            ground_truth_text = "\n---\n".join(ground_truth_messages)

        # Prepare ASR result data
        # Use matched_ground_truth if available for proper attempt tracking
        matched_ground_truth = ""
        if evaluation_results:
            matched_ground_truth = evaluation_results.get("matched_ground_truth", "")

        asr_data = {
            "session_id": request.session_id,
            "student_id": request.student_id,
            "video_id": request.video_id,
            "transcript": request.transcript,
            "ground_truth": matched_ground_truth
            or ground_truth_text,  # Use matched message for tracking
            "confidence": request.confidence,
            "audio_file_path": request.audio_file_path,
        }

        # Add evaluation results if available
        if evaluation_results:
            asr_data.update(
                {
                    "wer": evaluation_results["wer"],
                    "cer": evaluation_results["cer"],
                    "similarity_score": evaluation_results["similarity"],
                }
            )

        # Save to database
        asr_result_id = await DatabaseManager.save_asr_result(asr_data)

        # Update student progress - always update, even with low scores
        # The unlock logic is now based on time spent, not score threshold
        if evaluation_results:
            # Pass matched_ground_truth to track unique attempts
            background_tasks.add_task(
                StudentService.update_video_progress,
                request.student_id,
                request.video_id,
                True,  # completed
                evaluation_results["similarity"],
                matched_ground_truth,
            )

        response_data = {
            "success": True,
            "asr_result_id": asr_result_id,
            "message": "ASR result processed successfully",
            "transcript": request.transcript,
            "confidence": request.confidence,
        }

        # Add evaluation results to response
        if evaluation_results:
            response_data["evaluation"] = evaluation_results
            # Add matched_ground_truth to top level for frontend display
            response_data["matched_ground_truth"] = evaluation_results.get(
                "matched_ground_truth", ""
            )
            response_data["similarity_score"] = evaluation_results["similarity"]
            response_data["wer"] = evaluation_results["wer"]

        return response_data

    except Exception as e:
        print(f"❌ Error submitting ASR result: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process ASR result",
        )


@router.post("/evaluate")
async def evaluate_transcript(request: EvaluationRequest):
    """Evaluate a transcript against ground truth"""
    try:
        # Get ground truth messages if not provided
        ground_truth_messages = None
        if request.ground_truth:
            # Split provided ground truth by delimiter
            ground_truth_messages = [
                msg.strip() for msg in request.ground_truth.split("---") if msg.strip()
            ]
        else:
            ground_truth_messages = await VideoService.get_video_ground_truth(
                request.video_id
            )

        if not ground_truth_messages:
            return {
                "success": False,
                "message": "No ground truth available for this video",
                "video_id": request.video_id,
            }

        # Perform evaluation
        evaluation_results = await evaluate_transcription(
            request.transcript, ground_truth_messages
        )

        return {
            "success": True,
            "transcript": request.transcript,
            "ground_truth_messages": ground_truth_messages,
            "matched_ground_truth": evaluation_results.get("matched_ground_truth", ""),
            "evaluation": evaluation_results,
        }

    except Exception as e:
        print(f"❌ Error evaluating transcript: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to evaluate transcript",
        )


@router.get("/session/{session_id}/results")
async def get_session_results(session_id: str):
    """Get ASR results for a specific session"""
    try:
        # Validate session_id
        if not session_id or not session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID"
            )

        async with await DatabaseManager.get_connection() as db:
            import aiosqlite

            db.row_factory = aiosqlite.Row

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
                    "message": "No ASR results table found",
                }

            # Query the results
            async with db.execute(
                """
                SELECT * FROM asr_results WHERE session_id = ? ORDER BY timestamp DESC
            """,
                (session_id,),
            ) as cursor:
                results = await cursor.fetchall()

                # Process results to add matched_ground_truth
                processed_results = []
                for row in results:
                    result_dict = dict(row)

                    # Re-evaluate to get matched message if we have ground truth
                    if result_dict.get("ground_truth") and result_dict.get(
                        "transcript"
                    ):
                        ground_truth_messages = result_dict["ground_truth"].split(
                            "\n---\n"
                        )
                        ground_truth_messages = [
                            msg.strip() for msg in ground_truth_messages if msg.strip()
                        ]

                        if ground_truth_messages:
                            eval_result = await evaluate_transcription(
                                result_dict["transcript"], ground_truth_messages
                            )
                            result_dict["matched_ground_truth"] = eval_result.get(
                                "matched_ground_truth", ""
                            )

                    processed_results.append(result_dict)

                return {
                    "success": True,
                    "session_id": session_id,
                    "results": processed_results,
                    "count": len(processed_results),
                }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting session results: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session results: {str(e)}",
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
                "message": f"Ready for transcriptions. Log directory: {logs_dir}",
            }

        # Read the last few transcriptions
        transcriptions = []
        try:
            with open(asr_log_file, "r") as f:
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
            "log_file": str(asr_log_file),
        }

    except Exception as e:
        print(f"❌ Error getting live transcription: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get live transcription: {str(e)}",
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
                "student_id": student_id,
            }

        # Get directory paths
        logs_dir = await StudentService.get_student_logs_dir(student_id)
        audio_dir = await StudentService.get_student_audio_dir(student_id)
        asr_log_file = logs_dir / "asr_results.jsonl"

        # Check file/directory status
        debug_info = {
            "success": True,
            "student_data": {
                "id": student_data["id"],
                "name": student_data["name"],
                "student_id": student_data["student_id"],
            },
            "directories": {
                "logs_dir": str(logs_dir),
                "logs_dir_exists": logs_dir.exists(),
                "audio_dir": str(audio_dir),
                "audio_dir_exists": audio_dir.exists(),
                "asr_log_file": str(asr_log_file),
                "asr_log_file_exists": asr_log_file.exists(),
            },
        }

        # If log file exists, get some basic info
        if asr_log_file.exists():
            try:
                with open(asr_log_file, "r") as f:
                    lines = f.readlines()
                    debug_info["log_file_info"] = {
                        "line_count": len(lines),
                        "file_size_bytes": asr_log_file.stat().st_size,
                        "last_lines": [
                            line.strip() for line in lines[-3:] if line.strip()
                        ],
                    }
            except Exception as e:
                debug_info["log_file_error"] = str(e)

        # Check session config files
        session_config_dir = (
            Path(__file__).parent.parent.parent.parent / "data" / "asr_sessions"
        )
        session_config_file = session_config_dir / f"session_{student_id}.json"

        debug_info["session_config"] = {
            "config_dir": str(session_config_dir),
            "config_dir_exists": session_config_dir.exists(),
            "session_file": str(session_config_file),
            "session_file_exists": session_config_file.exists(),
        }

        if session_config_file.exists():
            try:
                with open(session_config_file, "r") as f:
                    import json

                    debug_info["session_config"]["content"] = json.load(f)
            except Exception as e:
                debug_info["session_config"]["error"] = str(e)

        return debug_info

    except Exception as e:
        print(f"❌ Error in debug endpoint: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e), "student_id": student_id}


@router.post("/start-buffered-recording")
async def start_buffered_recording(request: ASRSessionRequest):
    """Start buffered ASR recording (triggered by Control+Backtick)"""
    try:
        student_id = request.student_id

        # Check if already running and process is still alive
        if student_id in _asr_processes:
            existing_process = _asr_processes[student_id]["process"]
            # Check if process is still running
            if existing_process.poll() is None:
                print(
                    f"⚠️ ASR already running for student {student_id} (PID: {existing_process.pid})"
                )
                return {
                    "success": True,
                    "message": "ASR already running",
                    "student_id": student_id,
                    "pid": existing_process.pid,
                }
            else:
                # Process has ended, remove from dict
                print(f"🗑️ Cleaning up dead process for student {student_id}")
                del _asr_processes[student_id]

        # Get student directories
        audio_dir = await StudentService.get_student_audio_dir(student_id)
        logs_dir = await StudentService.get_student_logs_dir(student_id)
        audio_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Remove any existing stop flag from previous session
        stop_flag_file = logs_dir / ".asr_stop_recording"
        if stop_flag_file.exists():
            try:
                stop_flag_file.unlink()
                print(f"🗑️ Removed previous stop flag: {stop_flag_file}")
            except Exception as e:
                print(f"⚠️ Error removing stop flag: {e}")

        # Create session config
        session_config = {
            "student_id": student_id,
            "video_id": request.video_id,
            "session_id": request.session_id,
            "audio_dir": str(audio_dir),
            "logs_dir": str(logs_dir),
            "mode": "buffered",
        }

        # Store session config
        config_dir = project_root / "data" / "asr_sessions"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / f"session_{student_id}.json"

        with open(config_file, "w") as f:
            json.dump(session_config, f, indent=2)

        # Start the ASR service process
        vr_asr_script = project_root / "start_vr_asr.py"

        if not vr_asr_script.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VR ASR script not found",
            )

        # Double-check no other process is running for this student (even if not in dict)
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"start_vr_asr.py.*{student_id}"],
                capture_output=True,
                text=True,
            )
            if result.stdout.strip():
                existing_pids = result.stdout.strip().split("\n")
                print(
                    f"⚠️ Found existing ASR process(es) for {student_id}: {existing_pids}"
                )
                return {
                    "success": True,
                    "message": f"ASR already running (PIDs: {', '.join(existing_pids)})",
                    "student_id": student_id,
                }
        except Exception as e:
            print(f"⚠️ Could not check for existing processes: {e}")

        # Start process in its own process group (for easier cleanup)
        import os

        process = subprocess.Popen(
            [
                sys.executable,
                str(vr_asr_script),
                "--student-id",
                student_id,
                "--video-id",
                request.video_id or "",
                "--session-id",
                request.session_id or "",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=project_root,
            preexec_fn=os.setsid,  # Create new process group
        )

        # Store process
        _asr_processes[student_id] = {
            "process": process,
            "start_time": datetime.now().isoformat(),
            "config": session_config,
        }

        return {
            "success": True,
            "message": "Buffered ASR recording started",
            "student_id": student_id,
            "video_id": request.video_id,
            "pid": process.pid,
        }

    except Exception as e:
        print(f"❌ Error starting buffered recording: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start buffered recording: {str(e)}",
        )


@router.post("/stop-buffered-recording")
async def stop_buffered_recording(student_id: str):
    """Stop buffered ASR recording (triggered by Control+Backtick release)"""
    import os
    import signal

    try:
        # First, create stop flag to prevent further transcription writes
        student_logs_dir = await StudentService.get_student_logs_dir(student_id)
        stop_flag_file = student_logs_dir / ".asr_stop_recording"

        try:
            stop_flag_file.touch()
            print(f"🛑 Created stop flag: {stop_flag_file}")
        except Exception as e:
            print(f"⚠️ Error creating stop flag: {e}")

        if student_id not in _asr_processes:
            # Use pkill to kill any orphaned processes
            try:
                import subprocess as sp

                sp.run(["pkill", "-f", f"asr_service_vr.py.*{student_id}"], check=False)
                print(f"🔪 Killed any orphaned ASR processes for student: {student_id}")
            except Exception as e:
                print(f"❌ Error killing orphaned ASR processes: {e}")
                pass

            return {
                "success": True,
                "message": "No tracked process (cleaned up orphans and set stop flag)",
                "student_id": student_id,
            }

        process_info = _asr_processes[student_id]
        process = process_info["process"]
        pid = process.pid

        print(f"🔪 Stopping ASR process for student {student_id} (PID: {pid})")

        # Try to kill the process group (negative PID on Unix)
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            print(f"🔪 Sent SIGTERM to process group {pid}")
        except Exception as e:
            print(f"❌ Error killing process group: {e}")
            # Fallback: just kill the parent
            process.terminate()
            print(f"🔪 Sent terminate to process {pid}")

        # Wait for termination
        try:
            process.wait(timeout=3)
            print(f"✅ Process {pid} terminated")
        except subprocess.TimeoutExpired:
            # Force kill
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception as e:
                print(f"❌ Error force killing process: {e}")
                process.kill()
            print(f"🔪 Force killed process {pid}")

        # Also use pkill as backup to ensure children are killed
        try:
            import subprocess as sp

            sp.run(["pkill", "-f", f"asr_service_vr.py.*{student_id}"], check=False)
        except Exception as e:
            print(f"❌ Error killing orphaned ASR processes: {e}")
            pass

        # Remove from tracking
        del _asr_processes[student_id]

        return {
            "success": True,
            "message": "Buffered ASR recording stopped",
            "student_id": student_id,
        }

    except Exception as e:
        print(f"❌ Error stopping buffered recording: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop buffered recording: {str(e)}",
        )


# Helper functions


async def store_asr_session_config(config: Dict[str, Any]):
    """Store ASR session configuration for the ASR service to pick up"""
    config_dir = Path(__file__).parent.parent.parent.parent / "data" / "asr_sessions"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / f"session_{config['student_id']}.json"

    # Add timestamp
    config["created_at"] = datetime.now().isoformat()

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


async def evaluate_transcription(
    transcript: str, ground_truth_messages: list
) -> Dict[str, Any]:
    """Evaluate a transcription against ground truth using Levenshtein similarity per message"""
    try:
        # Import the evaluation functions
        from asr_evaluate import levenshtein_distance, normalize_text

        # Find best matching message using Levenshtein similarity
        normalized_transcript = normalize_text(transcript)
        best_match_index = -1
        best_similarity = 0.0
        best_ground_truth = ""

        per_message_scores = []

        for idx, gt_message in enumerate(ground_truth_messages):
            normalized_gt = normalize_text(gt_message)

            # Calculate Levenshtein similarity (0 to 1 scale)
            max_len = max(len(normalized_gt), len(normalized_transcript))
            if max_len == 0:
                similarity = 1.0
            else:
                edit_distance = levenshtein_distance(
                    normalized_gt, normalized_transcript
                )
                similarity = 1.0 - (edit_distance / max_len)

            per_message_scores.append(
                {
                    "message_index": idx,
                    "message": gt_message,
                    "similarity": round(similarity, 4),
                }
            )

            # Track best match
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_index = idx
                best_ground_truth = gt_message

        # Calculate overall metrics using best match
        if best_ground_truth:
            normalized_gt = normalize_text(best_ground_truth)
            max_len = max(len(normalized_gt), len(normalized_transcript))

            if max_len == 0:
                wer = 0.0
                cer = 0.0
                edit_distance = 0
            else:
                edit_distance = levenshtein_distance(
                    normalized_gt, normalized_transcript
                )
                # Approximate WER and CER from Levenshtein
                wer = edit_distance / max_len
                cer = edit_distance / max_len
        else:
            wer = 1.0
            cer = 1.0
            edit_distance = len(normalized_transcript)
            best_ground_truth = ""

        return {
            "wer": round(wer, 4),
            "cer": round(cer, 4),
            "word_accuracy": round(1.0 - wer, 4),
            "char_accuracy": round(1.0 - cer, 4),
            "similarity": round(best_similarity, 4),
            "edit_distance": edit_distance,
            "matched_message_index": best_match_index,
            "matched_ground_truth": best_ground_truth,
            "per_message_scores": per_message_scores,
        }

    except ImportError as e:
        print(f"❌ Error importing ASR evaluation: {e}")
        # Fallback to simple similarity calculation
        import re
        from difflib import SequenceMatcher

        def normalize_text(text):
            text = text.lower()
            text = re.sub(r"[^\w\s]", "", text)
            return " ".join(text.split())

        # Find best match using SequenceMatcher
        normalized_transcript = normalize_text(transcript)
        best_similarity = 0.0
        best_ground_truth = ""

        for gt_message in ground_truth_messages:
            normalized_gt = normalize_text(gt_message)
            similarity = SequenceMatcher(
                None, normalized_gt, normalized_transcript
            ).ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_ground_truth = gt_message

        return {
            "wer": round(1.0 - best_similarity, 4),
            "cer": round(1.0 - best_similarity, 4),
            "word_accuracy": round(best_similarity, 4),
            "char_accuracy": round(best_similarity, 4),
            "similarity": round(best_similarity, 4),
            "edit_distance": 0,
            "matched_ground_truth": best_ground_truth,
        }

    except Exception as e:
        print(f"❌ Error in transcript evaluation: {e}")
        import traceback

        traceback.print_exc()
        return {
            "wer": 1.0,
            "cer": 1.0,
            "word_accuracy": 0.0,
            "char_accuracy": 0.0,
            "similarity": 0.0,
            "edit_distance": len(transcript),
            "matched_ground_truth": "",
        }
