"""Authentication schemas."""

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    """Login form data."""

    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class UserCreate(BaseModel):
    """User creation data."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8)
    display_name: str | None = Field(None, max_length=100)


class UserResponse(BaseModel):
    """User data for responses."""

    id: int
    username: str
    display_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class SetupRequest(BaseModel):
    """Initial setup form data."""

    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)
    display_name: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def passwords_match(self) -> "SetupRequest":
        """Validate that password and password_confirm match."""
        if self.password != self.password_confirm:
            raise ValueError("Passwords do not match")
        return self
