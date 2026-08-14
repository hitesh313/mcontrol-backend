"""Auth business logic: registration, login, token refresh, forgot password."""
from datetime import datetime, timezone

from app.core.security import (
    create_access_token,
    generate_otp,
    generate_refresh_token,
    hash_otp,
    hash_password,
    hash_refresh_token,
    otp_expiry,
    refresh_token_expiry,
    verify_password,
)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import RegisterRequest, TokenResponse
from app.utils.exceptions import ConflictError, UnauthorizedError, ValidationAppError


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    # -- Registration ----------------------------------------------------
    def register(self, payload: RegisterRequest) -> dict:
        if self.user_repo.get_by_mobile(payload.mobile_number):
            raise ConflictError("An account with this mobile number already exists")
        if self.user_repo.get_by_email(payload.email):
            raise ConflictError("An account with this email already exists")

        user = self.user_repo.create({
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "mobile_number": payload.mobile_number,
            "email": payload.email,
            "password_hash": hash_password(payload.password),
        })
        return user

    # -- Login -------------------------------------------------------------
    def login(self, mobile_number: str, password: str) -> tuple[dict, TokenResponse]:
        user = self.user_repo.get_by_mobile(mobile_number)
        # Constant-shape error regardless of which check fails, to avoid
        # user-enumeration via response differences.
        if not user or not verify_password(password, user["password_hash"]):
            raise UnauthorizedError("Invalid mobile number or password")
        if not user["is_active"]:
            raise UnauthorizedError("This account has been deactivated")

        tokens = self._issue_tokens(user["id"])
        return user, tokens

    # -- Token refresh (rotation) -----------------------------------------
    def refresh(self, refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(refresh_token)
        stored = self.user_repo.get_refresh_token(token_hash)
        if not stored:
            raise UnauthorizedError("Invalid or expired refresh token")

        expires_at = datetime.fromisoformat(stored["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("Refresh token has expired")

        # Rotate: revoke old, issue new
        self.user_repo.revoke_refresh_token(stored["id"])
        return self._issue_tokens(stored["user_id"])

    def logout(self, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        stored = self.user_repo.get_refresh_token(token_hash)
        if stored:
            self.user_repo.revoke_refresh_token(stored["id"])

    # -- Forgot password -----------------------------------------------------
    def request_password_reset(self, mobile_number: str) -> str:
        """Returns the plaintext OTP so the caller can dispatch it via SMS.
        Silently no-ops (but returns a dummy) if the user doesn't exist, to
        avoid leaking account existence."""
        user = self.user_repo.get_by_mobile(mobile_number)
        otp = generate_otp()
        if user:
            self.user_repo.store_otp(user["id"], hash_otp(otp), otp_expiry())
        return otp

    def verify_otp(self, mobile_number: str, otp: str) -> bool:
        user = self.user_repo.get_by_mobile(mobile_number)
        if not user:
            return False
        record = self.user_repo.get_latest_otp(user["id"])
        if not record:
            return False
        if record["attempts"] >= 5:
            raise ValidationAppError("Too many attempts. Please request a new OTP")

        expires_at = datetime.fromisoformat(record["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return False

        if hash_otp(otp) != record["otp_hash"]:
            self.user_repo.increment_otp_attempts(record["id"], record["attempts"] + 1)
            return False
        return True

    def reset_password(self, mobile_number: str, otp: str, new_password: str) -> None:
        user = self.user_repo.get_by_mobile(mobile_number)
        if not user or not self.verify_otp(mobile_number, otp):
            raise UnauthorizedError("Invalid or expired OTP")

        record = self.user_repo.get_latest_otp(user["id"])
        self.user_repo.update_password(user["id"], hash_password(new_password))
        if record:
            self.user_repo.mark_otp_used(record["id"])
        # Invalidate all existing sessions after a password reset
        self.user_repo.revoke_all_refresh_tokens(user["id"])

    # -- Internal ------------------------------------------------------------
    def _issue_tokens(self, user_id: str) -> TokenResponse:
        access_token = create_access_token(user_id)
        refresh_token = generate_refresh_token()
        self.user_repo.store_refresh_token(
            user_id, hash_refresh_token(refresh_token), refresh_token_expiry()
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)
