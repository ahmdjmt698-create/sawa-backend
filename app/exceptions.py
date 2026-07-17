"""
استثناء مخصص يدعم error_code
"""
from fastapi import HTTPException, status


class APIException(HTTPException):
    """HTTPException مع error_code اختياري"""
    def __init__(
        self,
        status_code: int,
        detail: str = None,
        error_code: str = None,
        headers: dict = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code
