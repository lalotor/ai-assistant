# Comparison Engine

## Overview

The **Comparison Engine** is the core component responsible for computing differences between two data sets. It implements multiple diff algorithms and normalization strategies to provide accurate, meaningful comparisons.

---

## Architecture

### Hybrid Implementation

The comparison engine uses a **polyglot architecture**:

- **Python**: Orchestration, normalization, and preprocessing
- **Java**: High-performance diff computation

```
[Python Orchestrator]
        ↓
[Normalization Layer]
        ↓
[Java Diff Engine] ← High-performance computation
        ↓
[Result Formatter]
```

---

## Diff Algorithms

### 1. Structural Diff (v2.0 - Current)

**Status**: ✅ Implemented

**Description**: Line-by-line, character-level comparison of data structures.

#### Algorithm: Myers Diff

Implements the **Myers diff algorithm** for optimal edit distance:

```java
public class StructuralDiff {
    public DiffResult compute(String a, String b) {
        // Myers diff algorithm
        int[][] matrix = buildEditMatrix(a, b);
        List<DiffOperation> operations = backtrack(matrix, a, b);
        return new DiffResult(operations);
    }
    
    private int[][] buildEditMatrix(String a, String b) {
        int m = a.length();
        int n = b.length();
        int[][] dp = new int[m + 1][n + 1];
        
        for (int i = 0; i <= m; i++) dp[i][0] = i;
        for (int j = 0; j <= n; j++) dp[0][j] = j;
        
        for (int i = 1; i <= m; i++) {
            for (int j = 1; j <= n; j++) {
                if (a.charAt(i-1) == b.charAt(j-1)) {
                    dp[i][j] = dp[i-1][j-1];
                } else {
                    dp[i][j] = 1 + Math.min(
                        dp[i-1][j],    // deletion
                        Math.min(
                            dp[i][j-1],  // insertion
                            dp[i-1][j-1] // substitution
                        )
                    );
                }
            }
        }
        return dp;
    }
}
```

#### Features

✅ **Line-by-line comparison**  
✅ **Character-level precision**  
✅ **Optimal edit distance**  
✅ **Unified diff format**  
✅ **Context-aware output**  

#### Output Format

```diff
--- system_a.json
+++ system_b.json
@@ -10,7 +10,7 @@
   "transaction_id": "txn-abc-123",
   "user_id": "user-456",
-  "amount": 100.00,
+  "amount": 105.00,
   "currency": "USD",
   "status": "completed"
```

---

### 2. Semantic Diff (v3.0 - Planned)

**Status**: 🔄 In Development

**Description**: Meaning-based comparison using machine learning.

#### Planned Features

🔮 **Intent-based comparison**  
🔮 **Code refactoring detection**  
🔮 **Natural language diff summaries**  
🔮 **Semantic similarity scoring**  
🔮 **Context-aware analysis**  

#### Approach

```python
import transformers
from sentence_transformers import SentenceTransformer

class SemanticDiff:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def compute_similarity(self, text_a, text_b):
        """Compute semantic similarity score."""
        embedding_a = self.model.encode(text_a)
        embedding_b = self.model.encode(text_b)
        
        # Cosine similarity
        similarity = cosine_similarity(
            embedding_a.reshape(1, -1),
            embedding_b.reshape(1, -1)
        )[0][0]
        
        return similarity
    
    def detect_refactoring(self, code_a, code_b):
        """Detect if changes are refactoring."""
        # Extract AST representations
        ast_a = parse_ast(code_a)
        ast_b = parse_ast(code_b)
        
        # Compare semantic structure
        if are_semantically_equivalent(ast_a, ast_b):
            return {
                'is_refactoring': True,
                'type': 'variable_rename',
                'confidence': 0.95
            }
        return {'is_refactoring': False}
```

---

## Normalization Pipeline

### Why Normalization?

Normalization **reduces false positives** by standardizing data before comparison.

**Example**:
```python
# Without normalization
"  hello  " != "hello"  # Different!

# With normalization
normalize("  hello  ") == normalize("hello")  # Same!
```

### Normalization Stages

#### Stage 1: Whitespace Normalization

```python
def normalize_whitespace(text):
    """Standardize whitespace."""
    # Trim leading/trailing whitespace
    text = text.strip()
    
    # Normalize multiple spaces to single space
    text = re.sub(r'\s+', ' ', text)
    
    # Standardize line endings to LF
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    return text
```

#### Stage 2: Numeric Normalization

```python
def normalize_numbers(data):
    """Standardize numeric representations."""
    if isinstance(data, float):
        # Round to 2 decimal places
        return round(data, 2)
    
    if isinstance(data, str):
        # Convert string numbers to float
        try:
            num = float(data)
            return round(num, 2)
        except ValueError:
            return data
    
    return data
```

**Examples**:
- `1.0` → `1.00`
- `"1.999"` → `2.00`
- `1e2` → `100.00`

#### Stage 3: String Normalization

```python
def normalize_strings(text):
    """Standardize string representations."""
    # Unicode normalization (NFC)
    text = unicodedata.normalize('NFC', text)
    
    # Remove BOM markers
    text = text.replace('\ufeff', '')
    
    # Optional: case normalization
    if config.get('case_insensitive'):
        text = text.lower()
    
    return text
```

#### Stage 4: Structural Normalization

```python
def normalize_structure(data):
    """Canonicalize data structures."""
    if isinstance(data, dict):
        # Sort dictionary keys
        return {k: normalize_structure(v) 
                for k, v in sorted(data.items())}
    
    if isinstance(data, list):
        # Recursively normalize list elements
        return [normalize_structure(item) for item in data]
    
    return data
```

**Example**:
```python
# Before normalization
{"b": 2, "a": 1}

# After normalization
{"a": 1, "b": 2}
```

---

## Comparison Workflow

### End-to-End Process

```python
class ComparisonEngine:
    def compare(self, system_a_data, system_b_data, options):
        """Execute complete comparison workflow."""
        
        # Step 1: Normalization
        if options.get('normalization', True):
            system_a_data = self.normalize(system_a_data)
            system_b_data = self.normalize(system_b_data)
        
        # Step 2: Diff computation
        algorithm = options.get('algorithm', 'structural')
        if algorithm == 'structural':
            diff_result = self.structural_diff(system_a_data, system_b_data)
        elif algorithm == 'semantic':
            diff_result = self.semantic_diff(system_a_data, system_b_data)
        
        # Step 3: Result formatting
        formatted_result = self.format_result(diff_result, options)
        
        # Step 4: Compute statistics
        statistics = self.compute_statistics(diff_result)
        
        return {
            'match': len(diff_result.differences) == 0,
            'similarity_score': diff_result.similarity,
            'differences': formatted_result,
            'statistics': statistics
        }
    
    def normalize(self, data):
        """Apply all normalization stages."""
        data = normalize_whitespace(data)
        data = normalize_numbers(data)
        data = normalize_strings(data)
        data = normalize_structure(data)
        return data
```

---

## Diff Output Format

### JSON Diff Format

```json
{
  "match": false,
  "similarity_score": 0.92,
  "differences": [
    {
      "path": "data.amount",
      "type": "value_change",
      "old_value": 100.00,
      "new_value": 105.00,
      "severity": "medium",
      "context": {
        "line_number": 12,
        "surrounding_context": "..."
      }
    },
    {
      "path": "data.shipping.method",
      "type": "value_change",
      "old_value": "standard",
      "new_value": "express",
      "severity": "low"
    },
    {
      "path": "data.new_field",
      "type": "addition",
      "new_value": "some_value",
      "severity": "info"
    }
  ],
  "statistics": {
    "total_fields": 25,
    "changed_fields": 2,
    "added_fields": 1,
    "removed_fields": 0,
    "change_percentage": 8.0
  }
}
```

### Diff Types

| Type | Description | Example |
|------|-------------|----------|
| `value_change` | Field value modified | `100` → `105` |
| `addition` | New field added | `null` → `"value"` |
| `removal` | Field removed | `"value"` → `null` |
| `type_change` | Data type changed | `100` → `"100"` |

### Severity Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| `critical` | Breaking change | Schema incompatibility |
| `high` | Significant change | Core business logic |
| `medium` | Moderate change | Data value changes |
| `low` | Minor change | Formatting, metadata |
| `info` | Informational | Non-functional changes |

---

## Performance Optimization

### 1. Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor

def compare_batch(file_pairs):
    """Compare multiple file pairs in parallel."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(compare, a, b)
            for a, b in file_pairs
        ]
        results = [f.result() for f in futures]
    return results
```

### 2. Caching

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def compute_diff(data_a_hash, data_b_hash):
    """Cache diff results by content hash."""
    # Expensive diff computation
    return diff_result
```

### 3. Streaming for Large Files

```python
def compare_large_files(file_a, file_b, chunk_size=8192):
    """Stream and compare large files in chunks."""
    with open(file_a, 'r') as fa, open(file_b, 'r') as fb:
        while True:
            chunk_a = fa.read(chunk_size)
            chunk_b = fb.read(chunk_size)
            
            if not chunk_a and not chunk_b:
                break
            
            yield compare_chunks(chunk_a, chunk_b)
```

---

## Configuration

```yaml
comparison:
  # Algorithm selection
  algorithm: structural  # structural, semantic
  
  # Normalization settings
  normalization:
    enabled: true
    whitespace: true
    numbers: true
    strings: true
    structure: true
    case_sensitive: false
  
  # Diff format
  diff_format: unified  # unified, context, ndiff, json
  
  # Performance
  parallel_workers: 4
  cache_enabled: true
  chunk_size: 8192
```

---

## Related Documentation

- [Architecture Decisions](../DECISIONS.md) - Why normalization?
- [Async Processing](async-processing.md) - How comparisons are queued
- [Data Model](../architecture/data-model.md) - Diff result schema
