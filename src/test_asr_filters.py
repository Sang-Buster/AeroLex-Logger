#!/usr/bin/env python3
"""
ASR Quality Filter Tester
Analyze existing transcriptions and simulate different filter thresholds
"""

import json
import sys
from pathlib import Path


def load_transcriptions(jsonl_file):
    """Load transcriptions from JSONL file."""
    transcriptions = []
    with open(jsonl_file, "r") as f:
        for line in f:
            if line.strip():
                transcriptions.append(json.loads(line))
    return transcriptions


def analyze_transcriptions(
    transcriptions, min_confidence=0.55, min_length=10, min_words=3
):
    """Analyze which transcriptions would pass the filters."""
    passed = []
    filtered = []

    for t in transcriptions:
        transcript = t.get("transcript", "")
        confidence = t.get("confidence", 0.0)
        word_count = len(transcript.split())
        char_count = len(transcript.strip())

        reasons = []

        if confidence < min_confidence:
            reasons.append(f"Low confidence: {confidence:.3f} < {min_confidence}")

        if char_count < min_length:
            reasons.append(f"Too short: {char_count} chars < {min_length}")

        if word_count < min_words:
            reasons.append(f"Too few words: {word_count} < {min_words}")

        result = {
            "transcript": transcript,
            "confidence": confidence,
            "word_count": word_count,
            "char_count": char_count,
            "similarity": t.get("similarity_score", 0.0),
            "matched_gt": t.get("matched_ground_truth", ""),
        }

        if reasons:
            result["filter_reasons"] = reasons
            filtered.append(result)
        else:
            passed.append(result)

    return passed, filtered


def print_analysis(passed, filtered, threshold_label):
    """Print analysis results."""
    print(f"\n{'=' * 80}")
    print(f"  {threshold_label}")
    print(f"{'=' * 80}")

    total = len(passed) + len(filtered)
    print("\n📊 Summary:")
    print(f"  Total transcriptions: {total}")
    print(f"  ✅ Passed filters: {len(passed)} ({len(passed) / total * 100:.1f}%)")
    print(f"  ❌ Filtered out: {len(filtered)} ({len(filtered) / total * 100:.1f}%)")

    if filtered:
        print("\n🔇 Filtered Transcriptions:")
        print(f"{'─' * 80}")
        for i, t in enumerate(filtered, 1):
            print(f"\n{i}. '{t['transcript'][:70]}'")
            print(
                f"   Confidence: {t['confidence']:.3f} | Words: {t['word_count']} | Chars: {t['char_count']}"
            )
            print(f"   Similarity: {t['similarity']:.3f}")
            if t["matched_gt"]:
                print(f"   Ground truth: '{t['matched_gt'][:60]}'")
            print(f"   Reasons: {', '.join(t['filter_reasons'])}")

    if passed:
        print("\n✅ Accepted Transcriptions:")
        print(f"{'─' * 80}")
        for i, t in enumerate(passed, 1):
            print(f"\n{i}. '{t['transcript'][:70]}'")
            print(
                f"   Confidence: {t['confidence']:.3f} | Words: {t['word_count']} | Chars: {t['char_count']}"
            )
            print(f"   Similarity: {t['similarity']:.3f}")
            if t["matched_gt"]:
                print(f"   Ground truth: '{t['matched_gt'][:60]}'")


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_asr_filters.py <path_to_asr_results.jsonl>")
        print("\nExample:")
        print(
            "  python src/test_asr_filters.py logs/students/sang_123/asr_results.jsonl"
        )
        sys.exit(1)

    jsonl_file = Path(sys.argv[1])

    if not jsonl_file.exists():
        print(f"❌ File not found: {jsonl_file}")
        sys.exit(1)

    print(f"📂 Loading transcriptions from: {jsonl_file}")
    transcriptions = load_transcriptions(jsonl_file)
    print(f"📝 Loaded {len(transcriptions)} transcriptions")

    # Test different threshold configurations
    configs = [
        {
            "label": "Current Default Settings",
            "min_confidence": 0.55,
            "min_length": 10,
            "min_words": 3,
        },
        {
            "label": "Strict Filtering (Noisy Environment)",
            "min_confidence": 0.65,
            "min_length": 15,
            "min_words": 4,
        },
        {
            "label": "Lenient Filtering (Quiet Environment)",
            "min_confidence": 0.50,
            "min_length": 8,
            "min_words": 2,
        },
        {
            "label": "Aviation Radio Standard",
            "min_confidence": 0.60,
            "min_length": 20,
            "min_words": 4,
        },
    ]

    for config in configs:
        passed, filtered = analyze_transcriptions(
            transcriptions,
            config["min_confidence"],
            config["min_length"],
            config["min_words"],
        )
        print_analysis(passed, filtered, config["label"])

    # Print recommendation
    print(f"\n{'=' * 80}")
    print("  💡 Recommendations")
    print(f"{'=' * 80}")

    # Calculate statistics
    avg_confidence = sum(t.get("confidence", 0) for t in transcriptions) / len(
        transcriptions
    )
    avg_words = sum(len(t.get("transcript", "").split()) for t in transcriptions) / len(
        transcriptions
    )
    avg_similarity = sum(t.get("similarity_score", 0) for t in transcriptions) / len(
        transcriptions
    )

    print("\n📈 Statistics from your data:")
    print(f"  Average confidence: {avg_confidence:.3f}")
    print(f"  Average word count: {avg_words:.1f}")
    print(f"  Average similarity: {avg_similarity:.3f}")

    print("\n📝 Based on your data:")
    if avg_confidence < 0.6:
        print(f"  • Consider MIN_CONFIDENCE = {max(0.5, avg_confidence - 0.05):.2f}")
    else:
        print("  • Your confidence scores are good, keep MIN_CONFIDENCE = 0.55-0.60")

    if avg_similarity < 0.5:
        print("  • Low similarity scores detected - you may want stricter filters")
        print("  • Recommend: MIN_CONFIDENCE = 0.65, MIN_WORD_COUNT = 4")

    print("\n💡 To apply new settings:")
    print("  1. Edit asr_config.ini with your chosen values")
    print("  2. Restart the ASR service")
    print("  3. Test with new recordings and re-run this script")


if __name__ == "__main__":
    main()
