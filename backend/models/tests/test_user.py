from handler.auth.constants import DEFAULT_SCOPES, EDIT_SCOPES, FULL_SCOPES
from models.user import User


def test_admin(admin_user: User):
    assert admin_user.oauth_scopes == FULL_SCOPES


def test_editor(editor_user: User):
    assert editor_user.oauth_scopes == EDIT_SCOPES


def test_user(viewer_user: User):
    assert viewer_user.oauth_scopes == DEFAULT_SCOPES
