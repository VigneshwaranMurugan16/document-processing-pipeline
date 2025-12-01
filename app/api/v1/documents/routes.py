from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Document


router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_DIR = Path("storage")


@router.post("/upload", response_model=dict)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    saved_ids: list[int] = []

    for file in files:
        file_path = STORAGE_DIR / f"{datetime.utcnow().timestamp()}_{file.filename}"
        with file_path.open("wb") as buffer:
            buffer.write(await file.read())

        doc = Document(
            original_filename=file.filename,
            stored_path=str(file_path),
        )
        db.add(doc)
        await db.flush()
        saved_ids.append(doc.id)

    await db.commit()

    return {"uploaded_ids": saved_ids, "count": len(saved_ids)}


@router.get("/", response_model=list[dict])
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(select(Document))
    docs = result.scalars().all()

    return [
        {
            "id": d.id,
            "original_filename": d.original_filename,
            "stored_path": d.stored_path,
            "uploaded_at": d.uploaded_at.isoformat(),
        }
        for d in docs
    ]


@router.get("/{document_id}", response_model=dict)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": doc.id,
        "original_filename": doc.original_filename,
        "stored_path": doc.stored_path,
        "uploaded_at": doc.uploaded_at.isoformat(),
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.stored_path)

    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    return FileResponse(
        path=file_path,
        filename=doc.original_filename,
        media_type="application/octet-stream",
    )
