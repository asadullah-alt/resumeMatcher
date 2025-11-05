from fastapi import APIRouter, status, Depends

from app.core import get_db_session

health_check = APIRouter()


@health_check.get("/ping", tags=["Health check"], status_code=status.HTTP_200_OK)
async def ping(db = Depends(get_db_session)):
    """health check endpoint for MongoDB"""
    try:
        # Motor DB client ping
        await db.client.admin.command("ping")
        db_status = "reachable"
    except Exception:
        import logging
        logging.error("Database health check failed", exc_info=True)
        db_status = "unreachable"
    return {"message": "pong", "database": db_status}
