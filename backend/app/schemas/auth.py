from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegistrationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=320)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, value: str) -> str:
        has_uppercase = any(character.isupper() for character in value)
        has_lowercase = any(character.islower() for character in value)
        has_number = any(character.isdigit() for character in value)
        has_special_character = any(
            not character.isalnum() and not character.isspace() for character in value
        )

        if not all((has_uppercase, has_lowercase, has_number, has_special_character)):
            raise ValueError(
                "Password must include uppercase, lowercase, number, and special character"
            )
        return value


class RegisteredUserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}
