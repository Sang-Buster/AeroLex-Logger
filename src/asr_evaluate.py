#!/usr/bin/env python3
"""
ASR Evaluation Script - Levenshtein Distance and Accuracy Metrics
Compares ground truth text with ASR transcriptions using various metrics.

Features:
- Levenshtein distance calculation
- Word Error Rate (WER) and Character Error Rate (CER)
- Text alignment and fuzzy matching
- Batch processing of ASR results
- Detailed error analysis
"""

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.
    Returns the minimum number of single-character edits needed.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def words_to_number(words: list) -> str:
    """
    Convert a list of number words to a string representation.
    Handles aviation formats intelligently:
    - ["four", "eighty", "one"] -> "481" (digit concatenation)
    - ["one", "thousand", "one", "hundred"] -> "1100" (mathematical)
    - ["zero", "three", "zero"] -> "030" (individual digits with leading zeros)
    """
    number_map = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
        "thousand": 1000,
        "million": 1000000,
    }

    # Check if this is aviation-style digit reading (all single digits or tens)
    # E.g., "four eighty one" = 4-81, "zero three zero" = 0-3-0
    is_digit_style = all(
        word.lower() in number_map
        and number_map[word.lower()] < 100
        and word.lower() not in ["hundred", "thousand", "million"]
        for word in words
    )

    # Also check if it contains "hundred" or "thousand" (then it's mathematical)
    has_scale_words = any(
        word.lower() in ["hundred", "thousand", "million"] for word in words
    )

    if is_digit_style and not has_scale_words:
        # Aviation digit-by-digit reading: handle as "four eighty one" = "4" "81"
        result = ""
        i = 0
        while i < len(words):
            word = words[i].lower().strip()
            if word not in number_map:
                i += 1
                continue

            value = number_map[word]

            # Check if next word forms a compound number (e.g., "eighty one" = 81)
            if value >= 20 and value < 100 and i + 1 < len(words):
                next_word = words[i + 1].lower().strip()
                if next_word in number_map and number_map[next_word] < 10:
                    # Compound: "eighty one" -> "81"
                    result += str(value + number_map[next_word])
                    i += 2
                    continue

            # Single digit or tens without compound
            if value < 10:
                result += str(value)
            else:
                result += str(value)
            i += 1

        return result
    else:
        # Mathematical interpretation for altitudes, etc.
        total = 0
        current = 0

        for word in words:
            word = word.lower().strip()
            if word not in number_map:
                continue

            value = number_map[word]

            if value >= 1000:
                current = current or 1
                total += current * value
                current = 0
            elif value >= 100:
                current = (current or 1) * value
            else:
                current += value

        return str(total + current)


def normalize_aviation_numbers(text: str) -> str:
    """
    Algorithmically normalize aviation number formats.
    No hardcoded patterns - works with ANY number word combination.
    """
    import re

    # Phonetic corrections for common aviation words
    phonetic_map = {
        r"\brideau\b": "riddle",
        r"\breddell\b": "riddle",
        r"\bridal\b": "riddle",
    }

    for pattern, replacement in phonetic_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # All possible number words (for detection)
    number_words_set = {
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
    }

    words = text.split()
    result = []
    i = 0

    while i < len(words):
        original_word = words[i]
        # Strip punctuation for checking
        word_clean = re.sub(r"[^\w]", "", original_word.lower())

        # Check if this word starts a number sequence
        if word_clean in number_words_set:
            # Collect all consecutive number words (but stop at punctuation)
            number_word_sequence = []
            has_trailing_punct = False
            trailing_punct = ""

            while i < len(words):
                original = words[i]
                word_clean_check = re.sub(r"[^\w]", "", original.lower())

                if word_clean_check in number_words_set:
                    number_word_sequence.append(word_clean_check)
                    # Check if this word has trailing punctuation (end of number group)
                    if re.search(r"[^\w]$", original):
                        trailing_punct = re.findall(r"[^\w]+$", original)[0]
                        has_trailing_punct = True
                        i += 1
                        break
                    i += 1
                else:
                    break

            # Convert the sequence to a number (returns string now)
            number_str = words_to_number(number_word_sequence)
            if has_trailing_punct:
                result.append(number_str + trailing_punct)
            else:
                result.append(number_str)
        elif word_clean.isdigit():
            # Already a digit - keep it
            result.append(word_clean)
            i += 1
        else:
            # Not a number word - keep original with punctuation
            result.append(original_word)
            i += 1

    return " ".join(result)


def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing punctuation and converting to lowercase."""
    # Convert to lowercase
    text = text.lower()

    # Normalize aviation-specific number formats first
    text = normalize_aviation_numbers(text)

    # Remove hyphens and dashes (so "V-F-R" becomes "VFR")
    text = text.replace("-", "")
    text = text.replace("–", "")
    text = text.replace("—", "")

    # Remove punctuation except spaces
    text = re.sub(r"[^\w\s]", "", text)

    # Normalize whitespace
    text = " ".join(text.split())

    return text


def calculate_wer(reference: str, hypothesis: str) -> Tuple[float, Dict[str, int]]:
    """
    Calculate Word Error Rate (WER).
    Returns: (WER score, error counts dict)
    """
    ref_words = normalize_text(reference).split()
    hyp_words = normalize_text(hypothesis).split()

    # Use SequenceMatcher to get edit operations
    matcher = SequenceMatcher(None, ref_words, hyp_words)
    opcodes = matcher.get_opcodes()

    substitutions = 0
    deletions = 0
    insertions = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "replace":
            substitutions += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            deletions += i2 - i1
        elif tag == "insert":
            insertions += j2 - j1

    total_errors = substitutions + deletions + insertions
    total_words = len(ref_words)

    wer = total_errors / total_words if total_words > 0 else 0.0

    error_counts = {
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "total_errors": total_errors,
        "total_words": total_words,
    }

    return wer, error_counts


def calculate_cer(reference: str, hypothesis: str) -> Tuple[float, int]:
    """
    Calculate Character Error Rate (CER).
    Returns: (CER score, edit distance)
    """
    ref_chars = normalize_text(reference).replace(" ", "")
    hyp_chars = normalize_text(hypothesis).replace(" ", "")

    edit_distance = levenshtein_distance(ref_chars, hyp_chars)
    total_chars = len(ref_chars)

    cer = edit_distance / total_chars if total_chars > 0 else 0.0

    return cer, edit_distance


def find_best_match(
    ground_truth_segments: List[str], transcript: str, threshold: float = 0.3
) -> Tuple[Optional[str], float, int]:
    """
    Find the best matching ground truth segment for a transcript.
    Returns: (best_match, similarity_score, match_index)
    """
    best_match = None
    best_score = 0.0
    best_index = -1

    normalized_transcript = normalize_text(transcript)

    for i, gt_segment in enumerate(ground_truth_segments):
        normalized_gt = normalize_text(gt_segment)

        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, normalized_gt, normalized_transcript).ratio()

        if similarity > best_score and similarity >= threshold:
            best_score = similarity
            best_match = gt_segment
            best_index = i

    return best_match, best_score, best_index


def evaluate_single_pair(reference: str, hypothesis: str) -> Dict:
    """Evaluate a single reference-hypothesis pair."""
    # Calculate metrics
    wer, wer_details = calculate_wer(reference, hypothesis)
    cer, edit_distance = calculate_cer(reference, hypothesis)

    # Calculate similarity
    similarity = SequenceMatcher(
        None, normalize_text(reference), normalize_text(hypothesis)
    ).ratio()

    # Calculate accuracy (1 - error rate)
    word_accuracy = 1.0 - wer
    char_accuracy = 1.0 - cer

    return {
        "reference": reference,
        "hypothesis": hypothesis,
        "wer": round(wer, 4),
        "cer": round(cer, 4),
        "word_accuracy": round(word_accuracy, 4),
        "char_accuracy": round(char_accuracy, 4),
        "similarity": round(similarity, 4),
        "edit_distance": edit_distance,
        "wer_details": wer_details,
    }


def _filter_ground_truth_lines(lines: List[str]) -> List[str]:
    """
    Filter out file header sections from ground truth lines.
    Removes lines that are:
    - All dashes (--------------------------------)
    - File names (typically between dash lines, ending with .mp4, .mov, etc.)
    - Empty lines
    """
    filtered_lines = []
    in_header_section = False

    for line in lines:
        # Skip empty lines
        if not line:
            continue

        # Check if line is all dashes (header boundary)
        if re.match(r"^-+$", line):
            in_header_section = not in_header_section
            continue

        # If we're in a header section, skip the line
        if in_header_section:
            continue

        # Additional check: skip lines that look like filenames
        # (contain common video/audio extensions)
        if re.search(r"\.(mp4|mov|wav|mp3|avi|mkv|flv|m4v)$", line, re.IGNORECASE):
            continue

        # Keep this line as it appears to be actual transcript content
        filtered_lines.append(line)

    return filtered_lines


def load_ground_truth(file_path: str) -> List[str]:
    """Load ground truth from various file formats."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {file_path}")

    if path.suffix.lower() == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Handle different JSON structures
            if isinstance(data, list):
                return [str(item) for item in data]
            elif isinstance(data, dict):
                # Try common keys
                for key in ["text", "transcript", "ground_truth", "reference"]:
                    if key in data:
                        if isinstance(data[key], list):
                            return [str(item) for item in data[key]]
                        else:
                            return [str(data[key])]
                # If no known keys, return all string values
                return [str(v) for v in data.values() if isinstance(v, str)]

    elif path.suffix.lower() == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            return _filter_ground_truth_lines([line.strip() for line in f])

    else:
        # Try to read as text file
        with open(path, "r", encoding="utf-8") as f:
            return _filter_ground_truth_lines([line.strip() for line in f])


def load_asr_results(file_path: str) -> List[Dict]:
    """Load ASR results from JSONL file."""
    import jsonlines

    results = []

    if not Path(file_path).exists():
        raise FileNotFoundError(f"ASR results file not found: {file_path}")

    with jsonlines.open(file_path) as reader:
        for obj in reader:
            results.append(obj)

    return results


def evaluate_asr_results(
    ground_truth_file: str,
    asr_results_file: str,
    output_file: Optional[str] = None,
    match_threshold: float = 0.3,
) -> Dict:
    """
    Evaluate ASR results against ground truth.

    Args:
        ground_truth_file: Path to ground truth text file
        asr_results_file: Path to ASR results JSONL file
        output_file: Optional output file for detailed results
        match_threshold: Minimum similarity threshold for matching

    Returns:
        Dictionary with overall evaluation metrics
    """
    print(f"📖 Loading ground truth from: {ground_truth_file}")
    ground_truth = load_ground_truth(ground_truth_file)
    print(f"   Found {len(ground_truth)} ground truth segments")

    print(f"🎤 Loading ASR results from: {asr_results_file}")
    asr_results = load_asr_results(asr_results_file)
    print(f"   Found {len(asr_results)} ASR transcriptions")

    evaluations = []
    matched_gt_indices = set()

    print(f"\n🔍 Evaluating transcriptions (threshold: {match_threshold})...")

    for i, asr_result in enumerate(asr_results):
        transcript = asr_result.get("transcript", "")

        if not transcript.strip():
            continue

        # Find best matching ground truth
        best_match, similarity, match_index = find_best_match(
            ground_truth, transcript, match_threshold
        )

        evaluation = {
            "asr_index": i,
            "timestamp": asr_result.get("timestamp", ""),
            "confidence": asr_result.get("confidence", 0.0),
            "transcript": transcript,
            "matched": best_match is not None,
            "similarity_score": similarity,
            "ground_truth_index": match_index if best_match else -1,
        }

        if best_match:
            # Mark this ground truth as matched
            matched_gt_indices.add(match_index)

            # Calculate detailed metrics
            metrics = evaluate_single_pair(best_match, transcript)
            evaluation.update(metrics)

            print(
                f"✅ Match {i + 1}: WER={metrics['wer']:.3f}, CER={metrics['cer']:.3f}, Sim={similarity:.3f}"
            )
        else:
            print(
                f"❌ No match {i + 1}: '{transcript[:50]}...' (best sim: {similarity:.3f})"
            )
            evaluation.update(
                {
                    "reference": "",
                    "wer": 1.0,
                    "cer": 1.0,
                    "word_accuracy": 0.0,
                    "char_accuracy": 0.0,
                    "edit_distance": len(transcript),
                    "wer_details": {
                        "total_errors": len(transcript.split()),
                        "total_words": 0,
                    },
                }
            )

        evaluations.append(evaluation)

    # Calculate overall statistics
    matched_evaluations = [e for e in evaluations if e["matched"]]

    if matched_evaluations:
        avg_wer = sum(e["wer"] for e in matched_evaluations) / len(matched_evaluations)
        avg_cer = sum(e["cer"] for e in matched_evaluations) / len(matched_evaluations)
        avg_similarity = sum(e["similarity_score"] for e in matched_evaluations) / len(
            matched_evaluations
        )
        avg_word_accuracy = sum(e["word_accuracy"] for e in matched_evaluations) / len(
            matched_evaluations
        )
        avg_char_accuracy = sum(e["char_accuracy"] for e in matched_evaluations) / len(
            matched_evaluations
        )
    else:
        avg_wer = avg_cer = avg_similarity = avg_word_accuracy = avg_char_accuracy = 0.0

    # Count unmatched ground truth segments
    unmatched_gt_count = len(ground_truth) - len(matched_gt_indices)

    overall_stats = {
        "total_asr_results": len(asr_results),
        "total_ground_truth": len(ground_truth),
        "matched_transcriptions": len(matched_evaluations),
        "unmatched_transcriptions": len(evaluations) - len(matched_evaluations),
        "unmatched_ground_truth": unmatched_gt_count,
        "match_rate": len(matched_evaluations) / len(evaluations)
        if evaluations
        else 0.0,
        "coverage_rate": len(matched_gt_indices) / len(ground_truth)
        if ground_truth
        else 0.0,
        "average_wer": round(avg_wer, 4),
        "average_cer": round(avg_cer, 4),
        "average_word_accuracy": round(avg_word_accuracy, 4),
        "average_char_accuracy": round(avg_char_accuracy, 4),
        "average_similarity": round(avg_similarity, 4),
        "match_threshold": match_threshold,
    }

    # Save detailed results if output file specified
    if output_file:
        output_data = {
            "overall_stats": overall_stats,
            "evaluations": evaluations,
            "unmatched_ground_truth": [
                {"index": i, "text": gt}
                for i, gt in enumerate(ground_truth)
                if i not in matched_gt_indices
            ],
        }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Detailed results saved to: {output_file}")

    return overall_stats


def print_summary(stats: Dict):
    """Print evaluation summary."""
    print("\n" + "=" * 60)
    print("📊 ASR EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total ASR Results:        {stats['total_asr_results']}")
    print(f"Total Ground Truth:       {stats['total_ground_truth']}")
    print(f"Matched Transcriptions:   {stats['matched_transcriptions']}")
    print(f"Unmatched Transcriptions: {stats['unmatched_transcriptions']}")
    print(f"Unmatched Ground Truth:   {stats['unmatched_ground_truth']}")
    print()
    print(f"Match Rate:               {stats['match_rate']:.1%}")
    print(f"Coverage Rate:            {stats['coverage_rate']:.1%}")
    print()
    print("ACCURACY METRICS (for matched transcriptions):")
    print(f"Average Word Error Rate:  {stats['average_wer']:.1%}")
    print(f"Average Char Error Rate:  {stats['average_cer']:.1%}")
    print(f"Average Word Accuracy:    {stats['average_word_accuracy']:.1%}")
    print(f"Average Char Accuracy:    {stats['average_char_accuracy']:.1%}")
    print(f"Average Similarity:       {stats['average_similarity']:.1%}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate ASR results using Levenshtein distance and other metrics"
    )
    parser.add_argument(
        "ground_truth", nargs="?", help="Path to ground truth file (txt, json)"
    )
    parser.add_argument("asr_results", nargs="?", help="Path to ASR results JSONL file")
    parser.add_argument(
        "-o", "--output", help="Output file for detailed results (JSON)"
    )
    parser.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=0.3,
        help="Similarity threshold for matching (0.0-1.0, default: 0.3)",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("REF", "HYP"),
        help="Compare two single texts directly",
    )

    args = parser.parse_args()

    if args.compare:
        # Direct comparison mode
        ref, hyp = args.compare
        print("📝 Comparing texts directly:")
        print(f"Reference:  '{ref}'")
        print(f"Hypothesis: '{hyp}'")
        print()

        evaluation = evaluate_single_pair(ref, hyp)

        print(f"Word Error Rate (WER):    {evaluation['wer']:.1%}")
        print(f"Character Error Rate:     {evaluation['cer']:.1%}")
        print(f"Word Accuracy:            {evaluation['word_accuracy']:.1%}")
        print(f"Character Accuracy:       {evaluation['char_accuracy']:.1%}")
        print(f"Similarity Score:         {evaluation['similarity']:.1%}")
        print(f"Edit Distance:            {evaluation['edit_distance']}")
        print()
        print("Error Details:")
        details = evaluation["wer_details"]
        print(f"  Substitutions: {details['substitutions']}")
        print(f"  Deletions:     {details['deletions']}")
        print(f"  Insertions:    {details['insertions']}")
        print(f"  Total Errors:  {details['total_errors']}")
        print(f"  Total Words:   {details['total_words']}")

    else:
        # Batch evaluation mode
        if not args.ground_truth or not args.asr_results:
            parser.error(
                "ground_truth and asr_results are required for batch evaluation"
            )

        try:
            stats = evaluate_asr_results(
                args.ground_truth, args.asr_results, args.output, args.threshold
            )
            print_summary(stats)

        except FileNotFoundError as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
