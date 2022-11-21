import pytest

from middlewared.test.integration.utils import call, session, ssh, url


@pytest.fixture(scope="module")
def otp_enabled():
    call("auth.twofactor.update", {"enabled": True})

    try:
        yield
    finally:
        ssh("midclt call auth.twofactor.update '{\"enabled\": false}'")


def test_otp_http_basic_auth(otp_enabled):
    with session() as s:
        r = s.get(f"{url()}/api/v2.0/system/info/")
        assert r.status_code == 401
        assert r.text == "HTTP Basic Auth is unavailable when OTP is enabled"


def test_otp_http_basic_auth_upload(otp_enabled):
    with session() as s:
        r = s.get(f"{url()}/_upload/")
        assert r.status_code == 401
        assert r.text == "HTTP Basic Auth is unavailable when OTP is enabled"


