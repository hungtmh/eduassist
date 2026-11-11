from typing import Literal

from pydantic import BaseModel, Field

ConversationId = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    username: str
    role: Literal["student", "consultant", "academic", "accountant", "teacher", "manager"]
    display_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")


class Decision(BaseModel):
    type: Literal["approve", "reject"]
    message: str | None = Field(default=None, max_length=500)


class ResumeRequest(BaseModel):
    conversation_id: str = ConversationId
    decisions: list[Decision] = Field(min_length=1, max_length=50)
    run_id: str | None = Field(default=None, pattern=r"^[0-9a-f-]{36}$")


class FeedbackRequest(BaseModel):
    conversation_id: str = ConversationId
    run_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    score: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    saved: bool
    promoted_sql_examples: list[str]
