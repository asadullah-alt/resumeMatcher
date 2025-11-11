# Integration Points for Improvements Collection

## How to Update Your API Routes

If you have API endpoints that call `ScoreImprovementService.run()`, here's how to integrate the new caching:

### Current Implementation (Before)
```python
# app/api/router/v1/resume.py (example)

@router.post("/analyze/{resume_id}/{job_id}")
async def analyze_resume(resume_id: str, job_id: str):
    service = ScoreImprovementService(db)
    result = await service.run(resume_id, job_id)
    return result
```

### Updated Implementation (After - Option 1: Cache-First)
```python
# Default behavior - uses cache automatically
@router.post("/analyze/{resume_id}/{job_id}")
async def analyze_resume(resume_id: str, job_id: str):
    service = ScoreImprovementService(db)
    result = await service.run(resume_id, job_id)  # analyze_again=False by default
    return result
```

### Updated Implementation (After - Option 2: With Force Re-analyze)
```python
# Allow client to force re-analysis
@router.post("/analyze/{resume_id}/{job_id}")
async def analyze_resume(
    resume_id: str, 
    job_id: str,
    force_reanalyze: bool = False  # Query param to override cache
):
    service = ScoreImprovementService(db)
    result = await service.run(resume_id, job_id, analyze_again=force_reanalyze)
    return result
```

**Usage:**
- `/analyze/resume123/job456` - uses cache
- `/analyze/resume123/job456?force_reanalyze=true` - forces new analysis

### Updated Implementation (After - Option 3: With Streaming)
```python
from fastapi.responses import StreamingResponse

@router.post("/analyze/stream/{resume_id}/{job_id}")
async def analyze_resume_stream(
    resume_id: str, 
    job_id: str,
    force_reanalyze: bool = False
):
    service = ScoreImprovementService(db)
    return StreamingResponse(
        service.run_and_stream(resume_id, job_id, analyze_again=force_reanalyze),
        media_type="text/event-stream"
    )
```

## Router Integration Example

If you're updating the resume router, here's a complete example:

```python
# app/api/router/v1/resume.py

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.services import ScoreImprovementService
from app.services.exceptions import (
    ResumeNotFoundError,
    JobNotFoundError,
    ResumeParsingError,
    JobParsingError,
    ResumeKeywordExtractionError,
    JobKeywordExtractionError,
)

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/analyze/{resume_id}/{job_id}")
async def analyze_resume_with_cache(
    resume_id: str,
    job_id: str,
    force_reanalyze: bool = Query(False, description="Force re-analysis, ignoring cache"),
):
    """
    Analyze resume against job description with caching.
    
    Query Parameters:
    - force_reanalyze: If true, forces re-analysis even if cached result exists
    
    Returns:
    - Cached result if available (and force_reanalyze=false)
    - New analysis result otherwise
    """
    try:
        service = ScoreImprovementService(db=None)  # db param kept for compatibility
        result = await service.run(
            resume_id=resume_id,
            job_id=job_id,
            analyze_again=force_reanalyze
        )
        return {
            "success": True,
            "data": result,
            "cached": not force_reanalyze  # Client knows if result was cached
        }
    except ResumeNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Resume not found: {resume_id}")
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    except (ResumeParsingError, JobParsingError) as e:
        raise HTTPException(status_code=400, detail="Failed to parse resume or job")
    except (ResumeKeywordExtractionError, JobKeywordExtractionError) as e:
        raise HTTPException(status_code=400, detail="Failed to extract keywords")


@router.post("/analyze/stream/{resume_id}/{job_id}")
async def analyze_resume_stream(
    resume_id: str,
    job_id: str,
    force_reanalyze: bool = Query(False, description="Force re-analysis, ignoring cache"),
):
    """
    Stream resume analysis with progress updates.
    
    Returns server-sent events with progress updates and final result.
    """
    try:
        service = ScoreImprovementService(db=None)
        return StreamingResponse(
            service.run_and_stream(
                resume_id=resume_id,
                job_id=job_id,
                analyze_again=force_reanalyze
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"}
        )
    except (ResumeNotFoundError, JobNotFoundError, ResumeParsingError, JobParsingError) as e:
        raise HTTPException(status_code=404, detail=str(e))
```

## Database Setup

The `Improvement` model will be automatically initialized when your app starts (in the `init_db()` function):

```python
# app/core/database.py - Already updated
await init_beanie(
    database=_motor_db, 
    document_models=[
        Resume, 
        ProcessedResume, 
        Job, 
        ProcessedJob, 
        User,
        Improvement  # ← Automatically creates indexes
    ]
)
```

The indexes are created automatically by Beanie on first run.

## Migration Considerations

### Existing Data
- The `Improvement` collection starts empty
- No migration needed for existing documents
- Each new analysis creates a new `Improvement` record

### Index Creation
- Compound index on `(resume_id, job_id)` enables fast cache lookups
- Beanie creates indexes automatically on startup
- First startup may take slightly longer while indexes are built

## Monitoring & Debugging

### Check if caching is working
```python
# Query the Improvement collection directly
from app.models import Improvement

# Find cached results
improvement = await Improvement.find_one(
    (Improvement.resume_id == resume_id) & 
    (Improvement.job_id == job_id)
)
print(f"Cached: {improvement is not None}")
print(f"Last updated: {improvement.updated_at if improvement else 'N/A'}")
```

### Monitor cache hits
```python
# Count cached results
cached_count = await Improvement.find_all().count()
print(f"Total cached analyses: {cached_count}")
```

### Invalidate cache (if needed)
```python
# Delete specific cached result
await Improvement.find_one(
    (Improvement.resume_id == resume_id) & 
    (Improvement.job_id == job_id)
).delete()

# Clear all cache
await Improvement.delete_all()
```

## Testing

### Unit Test Example
```python
import pytest
from app.services import ScoreImprovementService
from app.models import Improvement

@pytest.mark.asyncio
async def test_caching_behavior(db):
    """Test that caching works correctly"""
    service = ScoreImprovementService(db)
    
    # First call - should analyze
    result1 = await service.run("resume_1", "job_1", analyze_again=False)
    assert result1 is not None
    
    # Verify it was saved
    cached = await Improvement.find_one(
        (Improvement.resume_id == "resume_1") & 
        (Improvement.job_id == "job_1")
    )
    assert cached is not None
    
    # Second call - should return same data
    result2 = await service.run("resume_1", "job_1", analyze_again=False)
    assert result1["original_score"] == result2["original_score"]
    assert result1["new_score"] == result2["new_score"]
    
    # Force reanalyze should skip cache
    result3 = await service.run("resume_1", "job_1", analyze_again=True)
    assert result3 is not None
```

## Performance Benchmarks

Expected performance after implementation:

```
Scenario 1: Cache Hit (no LLM calls)
  - Database lookup: ~10-50ms
  - Return to client: ~10-100ms
  - Total: <200ms ✓

Scenario 2: Cache Miss (full analysis)
  - Database queries: ~50ms
  - Embedding: ~5-15s
  - LLM improvement attempts: ~20-40s
  - Resume analysis LLM call: ~5-10s
  - Database saves: ~50ms
  - Total: ~30-65s (same as before)

Scenario 3: Stream Cache Hit
  - Database lookup: ~10-50ms
  - Send complete event: ~10-100ms
  - Total: <200ms ✓

Scenario 4: Stream Cache Miss
  - Full analysis with SSE: ~30-65s
  - Same as scenario 2, but with progress updates
```

## Backward Compatibility Checklist

- ✓ Default parameter `analyze_again=False` makes code backward compatible
- ✓ Existing calls to `run()` automatically benefit from caching
- ✓ No breaking changes to method signatures
- ✓ Error handling unchanged
- ✓ Database initialization handles new model automatically
