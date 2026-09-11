from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    display_name: str = Field(alias="displayName", min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("username", "display_name", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class RegisterData(BaseModel):
    status: str
    message: str


class LoginUser(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: str


class LoginData(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: LoginUser
