from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Document
from app.api.v1.documents.schemas import DocumentOut, UploadResult


router = APIRouter(prefix="/documents", tags=["documents"])

STORAGE_DIR = Path("storage")
MAX_FILE_SIZE_MB = 20
ALLOWED_CONTENT_TYPES = {"application/pdf"}


@router.post("/upload", response_model=UploadResult)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResult:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    saved_ids: list[int] = []

    for file in files:
        # Validate content type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Only PDF is allowed.",
            )

        # Read content once to enforce size limit
        contents = await file.read()
        size_mb = len(contents) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} is too large ({size_mb:.2f} MB). "
                       f"Max allowed is {MAX_FILE_SIZE_MB} MB.",
            )

        # Save to disk
        file_path = STORAGE_DIR / f"{datetime.utcnow().timestamp()}_{file.filename}"
        with file_path.open("wb") as buffer:
            buffer.write(contents)

        # Store metadata in DB
        doc = Document(
            original_filename=file.filename,
            stored_path=str(file_path),
        )
        db.add(doc)
        await db.flush()
        saved_ids.append(doc.id)

    await db.commit()

    return UploadResult(uploaded_ids=saved_ids, count=len(saved_ids))



@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    db: AsyncSession = Depends(get_db),
) -> list[DocumentOut]:
    result = await db.execute(select(Document))
    docs = result.scalars().all()
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentOut:
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentOut.model_validate(doc)


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
