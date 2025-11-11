# Quick Reference: New Improvements Collection

## Files Created/Modified

### Created
- `app/models/improvement.py` - New Improvement document model

### Modified
- `app/models/__init__.py` - Added Improvement export
- `app/core/database.py` - Registered Improvement model in Beanie
- `app/services/score_improvement_service.py` - Added caching logic

## Key API Changes

### `ScoreImprovementService.run()`
```python
async def run(
    self, 
    resume_id: str, 
    job_id: str, 
    analyze_again: bool = False
) -> Dict:
```

**Parameters:**
- `analyze_again=False` (default): Check cache first, return cached result if available
- `analyze_again=True`: Force new analysis, update cache with new result

### `ScoreImprovementService.run_and_stream()`
```python
async def run_and_stream(
    self, 
    resume_id: str, 
    job_id: str, 
    analyze_again: bool = False
) -> AsyncGenerator:
```

Same caching behavior as `run()`, but with streaming progress updates.

## Database Schema

**Collection Name:** `Improvement`

**Indexes:**
- `resume_id` - for finding all improvements for a resume
- `job_id` - for finding all improvements for a job
- `(resume_id, job_id)` - compound index for fast cache lookups ⭐
- `created_at` - for historical queries
- `updated_at` - for freshness tracking

## Cache Flow Diagram

```
run(resume_id, job_id, analyze_again)
    │
    ├─ If analyze_again == False
    │   │
    │   └─ Query: find(resume_id AND job_id)
    │       │
    │       ├─ Found: Return cached result ✓ FAST
    │       │
    │       └─ Not Found: Continue to analysis...
    │
    ├─ If analyze_again == True
    │   │
    │   └─ Skip cache check, force analysis...
    │
    └─ Run full analysis pipeline
        └─ Save/Update improvement document
```

## Common Use Cases

### Use Case 1: Get Latest Analysis (with caching)
```python
# Returns cached result if available, otherwise analyzes and caches
result = await service.run("resume_123", "job_456")
```

### Use Case 2: Force Fresh Analysis
```python
# Always re-analyzes, even if cached result exists
result = await service.run("resume_123", "job_456", analyze_again=True)
```

### Use Case 3: Stream Updates with Caching
```python
# If cached: streams completed status immediately
# If not cached: streams full pipeline with updates
async for event in service.run_and_stream("resume_123", "job_456"):
    handle_event(event)
```

## Backward Compatibility

✓ Fully backward compatible
- Existing calls: `service.run(resume_id, job_id)` automatically use caching
- Default behavior: `analyze_again=False` (cache-first approach)
- No code changes required for existing implementation

## Performance Notes

| Scenario | Method | Time | Notes |
|----------|--------|------|-------|
| Cached hit | `run()` | ~50ms | Database lookup only |
| Cache miss | `run()` | ~30-60s | Full LLM analysis |
| Force rerun | `run(analyze_again=True)` | ~30-60s | Full LLM analysis |
| Streaming cached | `run_and_stream()` | ~200ms | Sends result immediately |
| Streaming miss | `run_and_stream()` | ~30-60s | Full pipeline with updates |

## Query Examples

### Get cached improvement for a specific resume-job pair
```python
improvement = await Improvement.find_one(
    (Improvement.resume_id == "resume_123") & 
    (Improvement.job_id == "job_456")
)
```

### Get all improvements for a resume
```python
improvements = await Improvement.find(
    Improvement.resume_id == "resume_123"
).to_list()
```

### Get recent improvements
```python
recent = await Improvement.find_all().sort(
    [("updated_at", -1)]
).limit(10).to_list()
```

## Error Handling

Existing error handling remains unchanged:
- `ResumeNotFoundError` - if resume_id not found
- `JobNotFoundError` - if job_id not found
- `ResumeParsingError` - if resume not properly processed
- `JobParsingError` - if job not properly processed
- `ResumeKeywordExtractionError` - if keywords missing
- `JobKeywordExtractionError` - if keywords missing
