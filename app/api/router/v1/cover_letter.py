from fastapi import APIRouter, Depends, HTTPException, Body
from app.services.cover_letter_service import CoverLetterService
from app.core import init_db

cover_letter_router = APIRouter()

def get_cover_letter_service():
    # Since init_db initializes Beanie, we might not need to pass db explicitly 
    # if the service uses models directly. 
    # However, the service constructor expects 'db'. 
    # In main.py, init_db(app) is called.
    # We can pass a dummy or the actual client if needed, 
    # but based on other services, they seem to take 'db'.
    # Let's assume we can pass None or a placeholder if it's just for compatibility,
    # or better, let's check how other routers instantiate services.
    # Checking resume_router would have been good.
    # For now, I'll instantiate it.
    return CoverLetterService(db=None) 

@cover_letter_router.post("/getCoverletter")
async def get_cover_letter(
    token: str = Body(..., embed=True),
    resume_id: str = Body(..., embed=True),
    job_id: str = Body(..., embed=True),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    try:
        cover_letter = await service.generate_cover_letter(token, resume_id, job_id)
        return {"cover_letter": cover_letter}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@cover_letter_router.get("/")
async def read_cover_letter(
    job_id: str,
    resume_id: str,
    token: str,
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    try:
        cover_letter = await service.get_cover_letter(job_id, resume_id, token)
        if not cover_letter:
            raise HTTPException(status_code=404, detail="Cover letter not found")
        return {"cover_letter": cover_letter}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@cover_letter_router.put("/")
async def update_cover_letter(
    token: str = Body(..., embed=True),
    resume_id: str = Body(..., embed=True),
    job_id: str = Body(..., embed=True),
    content: str = Body(..., embed=True),
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    try:
        updated_content = await service.update_cover_letter(job_id, resume_id, token, content)
        if not updated_content:
            raise HTTPException(status_code=404, detail="Cover letter not found")
        return {"cover_letter": updated_content}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@cover_letter_router.delete("/")
async def delete_cover_letter(
    job_id: str,
    resume_id: str,
    token: str,
    service: CoverLetterService = Depends(get_cover_letter_service)
):
    try:
        success = await service.delete_cover_letter(job_id, resume_id, token)
        if not success:
            raise HTTPException(status_code=404, detail="Cover letter not found")
        return {"message": "Cover letter deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
