# tests/test_auth.py
#
# Tests for the GitHub OAuth + JWT auth system.

import pytest
from backend.auth.jwt import create_access_token, decode_access_token
from backend.auth.encryption import encrypt_token, decrypt_token


SECRET = "test-jwt-secret-for-ci-only-1234567890abcdef"


class TestJWT:
    """JWT creation and verification."""

    def test_create_and_decode(self):
        token = create_access_token(
            user_id="user-123",
            github_login="testuser",
            role="reviewer",
            secret=SECRET,
            expiry_hours=1,
        )
        claims = decode_access_token(token, SECRET)
        assert claims["sub"] == "user-123"
        assert claims["login"] == "testuser"
        assert claims["role"] == "reviewer"

    def test_wrong_secret_fails(self):
        token = create_access_token(
            user_id="user-123",
            github_login="testuser",
            role="reviewer",
            secret=SECRET,
        )
        import jwt
        with pytest.raises(jwt.InvalidSignatureError):
            decode_access_token(token, "wrong-secret")

    def test_expired_token_fails(self):
        token = create_access_token(
            user_id="user-123",
            github_login="testuser",
            role="reviewer",
            secret=SECRET,
            expiry_hours=-1,  # already expired
        )
        import jwt
        with pytest.raises(jwt.ExpiredSignatureError):
            decode_access_token(token, SECRET)


class TestEncryption:
    """Token encryption at rest."""

    def test_roundtrip(self):
        original = "ghp_abc123_my_github_token"
        encrypted = encrypt_token(original, SECRET)
        assert encrypted != original
        decrypted = decrypt_token(encrypted, SECRET)
        assert decrypted == original

    def test_wrong_key_fails(self):
        encrypted = encrypt_token("my-token", SECRET)
        with pytest.raises(ValueError, match="Cannot decrypt"):
            decrypt_token(encrypted, "wrong-key")

    def test_different_inputs_different_outputs(self):
        enc1 = encrypt_token("token-a", SECRET)
        enc2 = encrypt_token("token-b", SECRET)
        assert enc1 != enc2


class TestModels:
    """Database model imports work."""

    def test_user_model_importable(self):
        from backend.database.models import User
        assert User.__tablename__ == "users"

    def test_user_repo_model_importable(self):
        from backend.database.models import UserRepo
        assert UserRepo.__tablename__ == "user_repos"

    def test_pr_review_has_user_id(self):
        from backend.database.models import PRReviewRecord
        columns = [c.name for c in PRReviewRecord.__table__.columns]
        assert "user_id" in columns


class TestSettings:
    """New settings fields exist."""

    def test_oauth_settings_exist(self):
        from backend.config.settings import Settings
        fields = Settings.model_fields
        assert "github_oauth_client_id" in fields
        assert "github_oauth_client_secret" in fields
        assert "jwt_secret" in fields
        assert "jwt_expiry_hours" in fields
        assert "frontend_url" in fields
        assert "webhook_base_url" in fields


class TestWebhookModel:
    """Webhook model handles null body."""

    def test_null_body_becomes_empty_string(self):
        from backend.models.webhook import WebhookPullRequest
        pr = WebhookPullRequest(
            title="test",
            body=None,
            head={"sha": "abc123", "ref": "feature/test"},
            base={"ref": "main"},
            diff_url="https://github.com/test/test/pull/1.diff",
            user={"login": "testuser"},
        )
        assert pr.body == ""

    def test_normal_body_preserved(self):
        from backend.models.webhook import WebhookPullRequest
        pr = WebhookPullRequest(
            title="test",
            body="This is a PR description",
            head={"sha": "abc123", "ref": "feature/test"},
            base={"ref": "main"},
            diff_url="https://github.com/test/test/pull/1.diff",
            user={"login": "testuser"},
        )
        assert pr.body == "This is a PR description"
