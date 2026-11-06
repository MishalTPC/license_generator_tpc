"""TPC licensing regression tests. Author: Mishal Mohanlal; v0.1.0."""
from datetime import datetime, timedelta, timezone

import pytest

from tpc_licensing import (
    LicenceError, export_public_key, generate_signing_key, issue_licence,
    repository_name, save_licence, verify_licence,
)

ID1 = "12345678-90ABCDEF-12345678-90ABCDEF"
ID2 = "12345678-90ABCDEF-12345678-90ABCDE0"
START = datetime(2026, 11, 6, 10, 30, tzinfo=timezone.utc)


@pytest.fixture
def admin(tmp_path):
    key = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    generate_signing_key(key, "very-long-secure-password")
    export_public_key(key, "very-long-secure-password", public)
    return key, public


def _issue(admin, **kwargs):
    return issue_licence(admin[0], "very-long-secure-password", "smlz_to_robot", ID1, now=START, **kwargs)


def test_one_year_signature_valid(admin):
    licence = _issue(admin)
    payload = verify_licence(licence, admin[1], "smlz_to_robot", ID1, now=START + timedelta(days=300))
    assert payload["application"] == "smlz_to_robot"
    assert payload["expires_at"] == "2027-11-06T10:30:00Z"


def test_licence_expires_on_anniversary(admin):
    with pytest.raises(LicenceError, match="expired"):
        verify_licence(_issue(admin), admin[1], "smlz_to_robot", ID1, now=START.replace(year=2027))


def test_other_machine_rejected(admin):
    with pytest.raises(LicenceError, match="another computer"):
        verify_licence(_issue(admin), admin[1], "smlz_to_robot", ID2, now=START)


def test_other_application_rejected(admin):
    with pytest.raises(LicenceError, match="Licence is for"):
        verify_licence(_issue(admin), admin[1], "other_project", ID1, now=START)


def test_tampered_expiry_rejected(admin):
    licence = _issue(admin)
    licence["payload"]["expires_at"] = "2099-11-06T10:30:00Z"
    with pytest.raises(LicenceError, match="Signature invalid"):
        verify_licence(licence, admin[1], "smlz_to_robot", ID1, now=START)


def test_wrong_public_key_rejected(admin, tmp_path):
    otherkey = tmp_path / "other.pem"
    otherpub = tmp_path / "otherpublic.pem"
    generate_signing_key(otherkey, "another-secure-password")
    export_public_key(otherkey, "another-secure-password", otherpub)
    with pytest.raises(LicenceError, match="different issuer"):
        verify_licence(_issue(admin), otherpub, "smlz_to_robot", ID1, now=START)


def test_reject_github_owner_and_bad_id(admin):
    with pytest.raises(LicenceError, match="repository name only"):
        repository_name("MishalTPC/smlz_to_robot")
    with pytest.raises(LicenceError, match="Machine ID"):
        issue_licence(admin[0], "very-long-secure-password", "smlz_to_robot", "BAD", now=START)


def test_repo_case_canonical_and_file_roundtrip(admin, tmp_path):
    licence = issue_licence(admin[0], "very-long-secure-password", "SMLZ_TO_ROBOT", ID1, now=START)
    dest = save_licence(licence, tmp_path / "test.lic")
    assert verify_licence(dest, admin[1], "smlz_to_robot", ID1, now=START)["application"] == "smlz_to_robot"


def test_wrong_password_and_existing_key(admin):
    with pytest.raises(LicenceError, match="already exists"):
        generate_signing_key(admin[0], "very-long-secure-password")
    with pytest.raises(LicenceError, match="Check the key file and password"):
        export_public_key(admin[0], "bad password", admin[1])


def test_invalid_future_licence(admin):
    with pytest.raises(LicenceError, match="not yet active"):
        verify_licence(_issue(admin), admin[1], "smlz_to_robot", ID1, now=START - timedelta(minutes=1))
