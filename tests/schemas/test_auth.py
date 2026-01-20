"""Tests for authentication schemas."""

import pytest
from pydantic import ValidationError

from myriad.schemas.auth import LoginRequest, SetupRequest, UserCreate


class TestLoginRequest:
    """Tests for LoginRequest schema."""

    def test_valid_login(self):
        """Valid login credentials should pass."""
        login = LoginRequest(username="testuser", password="password123")
        assert login.username == "testuser"
        assert login.password == "password123"

    def test_empty_username_fails(self):
        """Empty username should fail validation."""
        with pytest.raises(ValidationError):
            LoginRequest(username="", password="password123")

    def test_empty_password_fails(self):
        """Empty password should fail validation."""
        with pytest.raises(ValidationError):
            LoginRequest(username="testuser", password="")


class TestUserCreate:
    """Tests for UserCreate schema."""

    def test_valid_user(self):
        """Valid user creation data should pass."""
        user = UserCreate(username="testuser", password="password123")
        assert user.username == "testuser"
        assert user.password == "password123"
        assert user.display_name is None

    def test_with_display_name(self):
        """User with display name should pass."""
        user = UserCreate(
            username="testuser",
            password="password123",
            display_name="Test User",
        )
        assert user.display_name == "Test User"

    def test_username_too_short(self):
        """Username less than 3 chars should fail."""
        with pytest.raises(ValidationError):
            UserCreate(username="ab", password="password123")

    def test_username_invalid_chars(self):
        """Username with special characters should fail."""
        with pytest.raises(ValidationError):
            UserCreate(username="test@user", password="password123")

    def test_password_too_short(self):
        """Password less than 8 chars should fail."""
        with pytest.raises(ValidationError):
            UserCreate(username="testuser", password="short")


class TestSetupRequest:
    """Tests for SetupRequest schema."""

    def test_valid_setup(self):
        """Valid setup data should pass."""
        setup = SetupRequest(
            username="testuser",
            password="password123",
            password_confirm="password123",
        )
        assert setup.username == "testuser"
        assert setup.password == "password123"

    def test_passwords_must_match(self):
        """Mismatched passwords should fail."""
        with pytest.raises(ValidationError) as exc_info:
            SetupRequest(
                username="testuser",
                password="password123",
                password_confirm="different456",
            )

        # Check that the error message is about password mismatch
        errors = exc_info.value.errors()
        assert any("match" in str(e["msg"]).lower() for e in errors)

    def test_username_validation_applied(self):
        """Username validation from UserCreate should apply."""
        with pytest.raises(ValidationError):
            SetupRequest(
                username="ab",  # Too short
                password="password123",
                password_confirm="password123",
            )

    def test_password_validation_applied(self):
        """Password length validation should apply."""
        with pytest.raises(ValidationError):
            SetupRequest(
                username="testuser",
                password="short",  # Too short
                password_confirm="short",
            )

    def test_with_display_name(self):
        """Setup with display name should pass."""
        setup = SetupRequest(
            username="testuser",
            password="password123",
            password_confirm="password123",
            display_name="Admin User",
        )
        assert setup.display_name == "Admin User"
