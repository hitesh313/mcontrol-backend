import re

from pydantic import BaseModel, EmailStr, field_validator, model_validator

MOBILE_REGEX = re.compile(r"^\+?[0-9]{10,15}$")


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    mobile_number: str
    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("mobile_number")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        if not MOBILE_REGEX.match(v):
            raise ValueError("Invalid mobile number format")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    mobile_number: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    mobile_number: str


class VerifyOtpRequest(BaseModel):
    mobile_number: str
    otp: str


class ResetPasswordRequest(BaseModel):
    mobile_number: str
    otp: str
    new_password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    mobile_number: str
    email: EmailStr
    is_active: bool
    is_verified: bool
