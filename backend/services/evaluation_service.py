#!/usr/bin/env python3
"""Utility helpers for aggregating ASR evaluation scores."""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Ensure src directory (contains asr_evaluate) is on path
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))

from asr_evaluate import (  # type: ignore  # noqa: E402
    levenshtein_distance,
    normalize_text,
)

MATCH_THRESHOLD = 0.3


def best_match_similarity(
    transcript: str,
    ground_truth_messages: Iterable[str],
    threshold: float = MATCH_THRESHOLD,
) -> Tuple[Optional[float], int]:
    """Return (similarity, message_index) for the best ground-truth match."""
    cleaned_transcript = normalize_text(transcript or "")
    if not cleaned_transcript:
        return None, -1

    best_similarity = 0.0
    best_index = -1

    for idx, gt_message in enumerate(ground_truth_messages):
        cleaned_ground_truth = normalize_text(gt_message or "")
        max_len = max(len(cleaned_ground_truth), len(cleaned_transcript))
        if max_len == 0:
            similarity = 1.0
        else:
            distance = levenshtein_distance(cleaned_ground_truth, cleaned_transcript)
            similarity = 1.0 - (distance / max_len)

        if similarity > best_similarity:
            best_similarity = similarity
            best_index = idx

    if best_index == -1 or best_similarity < threshold:
        return None, -1

    return round(best_similarity, 4), best_index


def aggregate_video_message_scores(
    asr_results: Iterable[Dict[str, object]],
    ground_truth_messages: Iterable[str],
    threshold: float = MATCH_THRESHOLD,
) -> Dict[int, float]:
    """Collect the best similarity per ground-truth message for a video."""
    scores: Dict[int, float] = {}
    ground_truth_list = list(ground_truth_messages)

    if not ground_truth_list:
        return scores

    for result in asr_results:
        transcript = str(result.get("transcript", ""))
        similarity, match_index = best_match_similarity(
            transcript, ground_truth_list, threshold
        )
        if similarity is None or match_index < 0:
            continue

        current_best = scores.get(match_index)
        if current_best is None or similarity > current_best:
            scores[match_index] = similarity

    return scores


def average_score_from_message_scores(message_scores: Dict[int, float]) -> float:
    """Compute the average score using matched message similarities."""
    if not message_scores:
        return 0.0
    total = sum(message_scores.values())
    average = total / len(message_scores)
    return round(average, 4)


def summarize_scores_by_video(
    asr_results: Iterable[Dict[str, object]],
    fetch_ground_truth,
    threshold: float = MATCH_THRESHOLD,
) -> Dict[str, Dict[str, object]]:
    """Summarize per-video message scores and averages.

    Returns mapping {video_id: {"message_scores": {idx: score}, "average": avg}}
    """
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for result in asr_results:
        video_id = str(result.get("video_id", ""))
        if not video_id:
            continue
        grouped[video_id].append(result)

    summary: Dict[str, Dict[str, object]] = {}

    for video_id, results in grouped.items():
        ground_truth = fetch_ground_truth(video_id)
        if not ground_truth:
            continue

        message_scores = aggregate_video_message_scores(
            results, ground_truth, threshold
        )
        average = average_score_from_message_scores(message_scores)

        summary[video_id] = {
            "message_scores": message_scores,
            "average": average,
        }

    return summary
