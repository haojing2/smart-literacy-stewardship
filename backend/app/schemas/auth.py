from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


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
