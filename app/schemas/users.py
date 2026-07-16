from pydantic import BaseModel, Field


class UpdateCurrentUserRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
