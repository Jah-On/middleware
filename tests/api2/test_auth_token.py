import io
import json

import pytest
import requests

import os
import sys
sys.path.append(os.getcwd())
from functions import GET
from auto_config import ip

from middlewared.test.integration.utils import call, client


@pytest.fixture(scope="module")
def download_token():
    return call("auth.generate_token", 300, {"filename": "debug.txz", "job": 1020})


def test_download_auth_token_cannot_be_used_for_restful_api_call(download_token):
    results = GET("/user/id/1/", anonymous=True, headers={"Authorization": f"Token {download_token}"})
    assert results.status_code == 403, results.text


def test_download_auth_token_cannot_be_used_for_upload(download_token):
    r = requests.post(
        f"http://{ip}/_upload",
        headers={"Authorization": f"Token {download_token}"},
        data={
            "data": json.dumps({
                "method": "filesystem.put",
                "params": ["/tmp/upload"],
            })
        },
        files={
            "file": io.BytesIO(b"test"),
        },
        timeout=10
    )
    assert r.status_code == 403


def test_download_auth_token_cannot_be_used_for_websocket_auth(download_token):
    with client(auth=None) as c:
        assert not c.call("auth.login_with_token", download_token)
