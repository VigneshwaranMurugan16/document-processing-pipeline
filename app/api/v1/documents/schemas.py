from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    original_filename: str
    stored_path: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class UploadResult(BaseModel):
    uploaded_ids: list[int]
    count: int
