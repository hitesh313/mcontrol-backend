from fastapi import APIRouter, status

from app.api.deps import DbSession
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    VerifyOtpRequest,
)
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _service(db: DbSession) -> AuthService:
    return AuthService(UserRepository(db))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession):
    user = _service(db).register(payload)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession):
    _user, tokens = _service(db).login(payload.mobile_number, payload.password)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: DbSession):
    return _service(db).refresh(payload.refresh_token)


@router.post("/logout", response_model=MessageResponse)
def logout(payload: RefreshTokenRequest, db: DbSession):
    _service(db).logout(payload.refresh_token)
    return MessageResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, db: DbSession):
    otp = _service(db).request_password_reset(payload.mobile_number)
    # TODO: dispatch `otp` via SMS provider (e.g. Twilio/MSG91) inside
    # app/notifications — never return it in the API response in production.
    return MessageResponse(message="If the account exists, an OTP has been sent")


@router.post("/verify-otp", response_model=MessageResponse)
def verify_otp(payload: VerifyOtpRequest, db: DbSession):
    valid = _service(db).verify_otp(payload.mobile_number, payload.otp)
    if not valid:
        from app.utils.exceptions import UnauthorizedError
        raise UnauthorizedError("Invalid or expired OTP")
    return MessageResponse(message="OTP verified")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, db: DbSession):
    _service(db).reset_password(payload.mobile_number, payload.otp, payload.new_password)
    return MessageResponse(message="Password reset successfully")
