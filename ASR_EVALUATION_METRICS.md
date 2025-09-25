# ASR Evaluation Metrics Documentation

This document explains how the various evaluation metrics are computed in the ASR evaluation script (`asr_evaluate.py`). These metrics are essential for measuring the accuracy and quality of Automatic Speech Recognition (ASR) systems.

## Overview

The evaluation script computes several key metrics to assess ASR performance:

- **Word Error Rate (WER)** - Primary metric for word-level accuracy
- **Character Error Rate (CER)** - Character-level accuracy metric
- **Similarity Score** - Overall text similarity measure
- **Word/Character Accuracy** - Accuracy percentages (1 - error rate)
- **Levenshtein Distance** - Edit distance between texts

## Text Normalization

Before computing any metrics, both the reference (ground truth) and hypothesis (ASR output) texts are normalized to ensure fair comparison.

### Normalization Process

```python
def normalize_text(text: str) -> str:
    # 1. Convert to lowercase
    text = text.lower()
    # 2. Remove punctuation and special characters
    text = re.sub(r'[^\w\s]', '', text)
    # 3. Normalize whitespace (collapse multiple spaces)
    text = ' '.join(text.split())
    return text
```

### Example

```
Original:    "Hello, World! How are you today?"
Normalized:  "hello world how are you today"
```

## Word Error Rate (WER)

WER is the most commonly used metric for evaluating ASR systems. It measures the percentage of words that were incorrectly recognized.

### Formula

```
WER = (S + D + I) / N
```

Where:

- `S` = Number of substitutions
- `D` = Number of deletions
- `I` = Number of insertions
- `N` = Total number of words in reference

### Algorithm

1. Normalize both reference and hypothesis texts
2. Split into word lists
3. Use sequence alignment (SequenceMatcher) to find edit operations
4. Count substitutions, deletions, and insertions
5. Calculate WER as total errors divided by reference word count

### Example Calculation

**Reference:** "the quick brown fox jumps"  
**Hypothesis:** "the quick red fox"

**Step 1: Normalize and split**

- Ref words: `["the", "quick", "brown", "fox", "jumps"]` (N=5)
- Hyp words: `["the", "quick", "red", "fox"]`

**Step 2: Alignment**

```
Ref: the  quick  brown  fox  jumps
Hyp: the  quick  red    fox  -
     ✓    ✓      S      ✓    D
```

**Step 3: Count errors**

- Substitutions (S): 1 ("brown" → "red")
- Deletions (D): 1 ("jumps" deleted)
- Insertions (I): 0
- Total errors: 2

**Step 4: Calculate WER**

```
WER = (1 + 1 + 0) / 5 = 2/5 = 0.4 = 40%
```

## Character Error Rate (CER)

CER measures accuracy at the character level, which can be more appropriate for some languages or applications.

### Formula

```
CER = Levenshtein_Distance(ref_chars, hyp_chars) / len(ref_chars)
```

### Algorithm

1. Normalize both texts
2. Remove spaces to get character sequences
3. Calculate Levenshtein distance between character sequences
4. Divide by reference character count

### Example Calculation

**Reference:** "hello world"  
**Hypothesis:** "helo word"

**Step 1: Normalize and remove spaces**

- Ref chars: `"helloworld"` (10 characters)
- Hyp chars: `"heloword"` (8 characters)

**Step 2: Calculate Levenshtein distance**

```
helloworld
helo-wor-d
    ↓  ↓ ↓
   del del ins
```

Operations needed: 2 deletions, 1 insertion = 3 total

**Step 3: Calculate CER**

```
CER = 3 / 10 = 0.3 = 30%
```

## Levenshtein Distance

The Levenshtein distance calculates the minimum number of single-character edits (insertions, deletions, substitutions) needed to transform one string into another.

### Algorithm (Dynamic Programming)

```python
def levenshtein_distance(s1: str, s2: str) -> int:
    # Create matrix of size (len(s1)+1) x (len(s2)+1)
    # dp[i][j] = min edits to transform s1[:i] to s2[:j]

    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]
```

### Example Matrix

For `s1="cat"` and `s2="dog"`:

```
    ""  d  o  g
""   0  1  2  3
c    1  1  2  3
a    2  2  2  3
t    3  3  3  3
```

Result: Levenshtein distance = 3 (all characters different)

## Similarity Score

The similarity score provides an intuitive measure of how similar two texts are, ranging from 0.0 (completely different) to 1.0 (identical).

### Algorithm

Uses Python's `difflib.SequenceMatcher.ratio()` which calculates:

```
Similarity = 2 * M / T
```

Where:

- `M` = Number of matching characters/elements
- `T` = Total number of characters/elements in both sequences

### Example

**Reference:** "the quick brown fox"  
**Hypothesis:** "the quick red fox"

**Step 1: Normalize**

- Ref: `"the quick brown fox"`
- Hyp: `"the quick red fox"`

**Step 2: Find matching subsequences**

- Matching: "the quick " + " fox" = 13 characters
- Total length: 18 + 16 = 34 characters

**Step 3: Calculate similarity**

```
Similarity = 2 * 13 / 34 = 26/34 ≈ 0.76 = 76%
```

## Accuracy Metrics

Accuracy metrics are simply the complement of error rates:

- **Word Accuracy** = 1 - WER
- **Character Accuracy** = 1 - CER

### Example

If WER = 0.15 (15%), then Word Accuracy = 0.85 (85%)

## Fuzzy Matching Process

The evaluation script uses fuzzy matching to pair ASR outputs with ground truth segments:

### Algorithm

1. For each ASR transcript, calculate similarity with all ground truth segments
2. Find the best match above a threshold (default: 0.3)
3. Use the best match for detailed metric calculation
4. Track which ground truth segments remain unmatched

### Example

**Ground Truth Segments:**

1. "Welcome to our flight training program"
2. "Please fasten your seatbelt"
3. "We are now ready for takeoff"

**ASR Output:** "Welcome to the flight training program"

**Similarity Scores:**

- vs. Segment 1: 0.89 (best match, above threshold)
- vs. Segment 2: 0.12 (below threshold)
- vs. Segment 3: 0.15 (below threshold)

Result: ASR output is matched with Segment 1 for detailed evaluation.

## Overall Evaluation Statistics

The script calculates aggregate statistics across all matched transcriptions:

- **Match Rate**: Percentage of ASR outputs that found a ground truth match
- **Coverage Rate**: Percentage of ground truth segments that were matched
- **Average Metrics**: Mean WER, CER, accuracy, and similarity across matched pairs

### Example Summary

```
📊 ASR EVALUATION SUMMARY
=====================================
Total ASR Results:        15
Total Ground Truth:       12
Matched Transcriptions:   10
Unmatched Transcriptions: 5
Unmatched Ground Truth:   2

Match Rate:               66.7%
Coverage Rate:            83.3%

ACCURACY METRICS (for matched transcriptions):
Average Word Error Rate:  12.5%
Average Char Error Rate:  8.3%
Average Word Accuracy:    87.5%
Average Char Accuracy:    91.7%
Average Similarity:       84.2%
```

## Usage Examples

### Direct Text Comparison

```bash
python asr_evaluate.py --compare "hello world" "hello word"
```

Output:

```
Word Error Rate (WER):    20.0%
Character Error Rate:     9.1%
Word Accuracy:            80.0%
Character Accuracy:       90.9%
Similarity Score:         81.8%
Edit Distance:            1
```

### Batch Evaluation

```bash
python asr_evaluate.py ground_truth.txt asr_results.jsonl -o detailed_results.json -t 0.3
```

This compares all ASR results against ground truth with a similarity threshold of 0.3.

## Best Practices

1. **Normalization**: Always normalize text before comparison to avoid penalizing for punctuation/case differences
2. **Threshold Selection**: Choose similarity thresholds based on your domain (0.3 is conservative, 0.5+ is stricter)
3. **Multiple Metrics**: Use multiple metrics (WER, CER, similarity) for comprehensive evaluation
4. **Error Analysis**: Review unmatched segments to understand system limitations
5. **Context Consideration**: Remember that perfect transcription isn't always necessary - functional accuracy matters more in some applications

## Implementation Notes

- The script uses `difflib.SequenceMatcher` for sequence alignment, which implements a variant of the longest common subsequence algorithm
- Levenshtein distance is computed using dynamic programming for efficiency
- Text normalization is aggressive (removes all punctuation) - adjust based on your evaluation needs
- The fuzzy matching process helps handle cases where ASR outputs don't perfectly align with ground truth segments
