# ASR Evaluation Script

This script computes Levenshtein distance and other accuracy metrics to evaluate ASR transcription quality against ground truth data.

## Features

- **Levenshtein Distance**: Character-level edit distance
- **Word Error Rate (WER)**: Industry standard for speech recognition
- **Character Error Rate (CER)**: Character-level accuracy
- **Text Alignment**: Fuzzy matching for multiple text segments
- **Batch Processing**: Process entire ASR result files
- **Detailed Analysis**: Error breakdowns and unmatched segments

## Usage

### 1. Batch Evaluation (Recommended)

Compare your ASR results against ground truth:

```bash
# Basic evaluation
uv run python evaluate_asr.py example_ground_truth.txt logs/asr_results.jsonl

# With detailed output and custom threshold
uv run python evaluate_asr.py example_ground_truth.txt logs/asr_results.jsonl -o detailed_results.json -t 0.4
```

### 2. Direct Text Comparison

Compare two specific texts:

```bash
uv run python evaluate_asr.py --compare "Hello world" "Hello word"
```

## Ground Truth File Formats

### Text File (.txt)
```
Hello world
This is a test
Aviation communication
```

### JSON File (.json)
```json
{
  "ground_truth": [
    "Hello world",
    "This is a test", 
    "Aviation communication"
  ]
}
```

Or simple list:
```json
[
  "Hello world",
  "This is a test",
  "Aviation communication"
]
```

## Output Metrics

- **WER (Word Error Rate)**: Percentage of words that are wrong
- **CER (Character Error Rate)**: Percentage of characters that are wrong
- **Word/Character Accuracy**: 1 - Error Rate
- **Similarity Score**: Overall text similarity (0-1)
- **Match Rate**: Percentage of transcriptions matched to ground truth
- **Coverage Rate**: Percentage of ground truth covered by transcriptions

## Example Output

```
📊 ASR EVALUATION SUMMARY
============================================================
Total ASR Results:        6
Total Ground Truth:       10
Matched Transcriptions:   5
Unmatched Transcriptions: 1
Unmatched Ground Truth:   5

Match Rate:               83.3%
Coverage Rate:            50.0%

ACCURACY METRICS (for matched transcriptions):
Average Word Error Rate:  15.2%
Average Char Error Rate:  8.1%
Average Word Accuracy:    84.8%
Average Character Accuracy: 91.9%
Average Similarity:       87.4%
```

## Parameters

- `-t, --threshold`: Similarity threshold for matching (0.0-1.0, default: 0.3)
- `-o, --output`: Save detailed results to JSON file
- `--compare`: Direct comparison mode for two texts

## How Matching Works

The script uses fuzzy matching to align ASR transcriptions with ground truth segments:

1. **Normalization**: Removes punctuation, converts to lowercase
2. **Similarity Calculation**: Uses SequenceMatcher for text similarity
3. **Threshold Matching**: Only matches above similarity threshold
4. **Best Match Selection**: Finds highest similarity ground truth for each transcription

This handles cases where users speak segments in different order or with variations.
