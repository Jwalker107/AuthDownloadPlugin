"""
automated test for AuthDownloadPlugin.py
"""

import base64
import copy
import json
import os
import sys

# add repo root path to be available for import
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# import the main python module for this repo AuthDownloadPlugin.py
import AuthDownloadPlugin


class _FakeCredential:
    def __init__(self, password: str):
        self.password = password


class _InMemoryKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        if service not in self.store:
            self.store[service] = {}
        self.store[service][username] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get(service, {}).get(username, None)

    def get_credential(self, service: str, username: str):
        password = self.get_password(service, username)
        if password is None:
            return None
        return _FakeCredential(password)


def _run_with_fake_keyring(test_func) -> None:
    fake_keyring = _InMemoryKeyring()
    original_set_password = AuthDownloadPlugin.keyring.set_password
    original_get_password = AuthDownloadPlugin.keyring.get_password
    original_get_credential = AuthDownloadPlugin.keyring.get_credential
    AuthDownloadPlugin.keyring.set_password = fake_keyring.set_password
    AuthDownloadPlugin.keyring.get_password = fake_keyring.get_password
    AuthDownloadPlugin.keyring.get_credential = fake_keyring.get_credential
    try:
        test_func()
    finally:
        AuthDownloadPlugin.keyring.set_password = original_set_password
        AuthDownloadPlugin.keyring.get_password = original_get_password
        AuthDownloadPlugin.keyring.get_credential = original_get_credential


def _write_temp_config(config: dict) -> str:
    temp_config_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "tmp-config.json"
    )
    with open(temp_config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return temp_config_path


def _remove_temp_config(config_path: str) -> None:
    if os.path.exists(config_path):
        os.remove(config_path)


def test_basic_auth_headers() -> None:
    def _test() -> None:
        config = {
            "plugin_name": "AuthDownloadPlugin",
            "url_configs": [
                {
                    "config_name": "basic-only",
                    "url_list": ["https://example\\.com/.*"],
                    "Basic-Auth": {
                        "username": "MyAccount",
                        "password": "MyPassword"
                    }
                }
            ]
        }

        config_path = _write_temp_config(copy.deepcopy(config))
        try:
            AuthDownloadPlugin.update_credentials(config, config_path)
            headers = AuthDownloadPlugin.get_request_headers(config, config["url_configs"][0])
            expected = base64.b64encode(b"MyAccount:MyPassword").decode("ascii")
            if headers.get("Authorization") != f"Basic {expected}":
                raise AssertionError("Basic authorization header was not assembled correctly")
        finally:
            _remove_temp_config(config_path)

    _run_with_fake_keyring(_test)


def test_custom_headers() -> None:
    def _test() -> None:
        config = {
            "plugin_name": "AuthDownloadPlugin",
            "url_configs": [
                {
                    "config_name": "header-only",
                    "url_list": ["https://example\\.com/.*"],
                    "Header": {
                        "X-Api-Key": "header-secret",
                        "Accept": "application/octet-stream"
                    }
                }
            ]
        }

        config_path = _write_temp_config(copy.deepcopy(config))
        try:
            AuthDownloadPlugin.update_credentials(config, config_path)
            headers = AuthDownloadPlugin.get_request_headers(config, config["url_configs"][0])
            if headers.get("X-Api-Key") != "header-secret":
                raise AssertionError("X-Api-Key header missing or incorrect")
            if headers.get("Accept") != "application/octet-stream":
                raise AssertionError("Accept header missing or incorrect")
        finally:
            _remove_temp_config(config_path)

    _run_with_fake_keyring(_test)


def test_basic_and_custom_headers() -> None:
    def _test() -> None:
        config = {
            "plugin_name": "AuthDownloadPlugin",
            "url_configs": [
                {
                    "config_name": "basic-and-header",
                    "url_list": ["https://example\\.com/.*"],
                    "Basic-Auth": {
                        "username": "MyAccount",
                        "password": "MyPassword"
                    },
                    "Header": {
                        "X-Custom": "custom-value"
                    }
                }
            ]
        }

        config_path = _write_temp_config(copy.deepcopy(config))
        try:
            AuthDownloadPlugin.update_credentials(config, config_path)
            headers = AuthDownloadPlugin.get_request_headers(config, config["url_configs"][0])
            expected = base64.b64encode(b"MyAccount:MyPassword").decode("ascii")
            if headers.get("Authorization") != f"Basic {expected}":
                raise AssertionError("Basic authorization header missing in combined auth test")
            if headers.get("X-Custom") != "custom-value":
                raise AssertionError("Custom header missing in combined auth test")
        finally:
            _remove_temp_config(config_path)

    _run_with_fake_keyring(_test)


def test_missing_keyring_values_failures() -> None:
    def _test() -> None:
        missing_basic_config = {
            "plugin_name": "AuthDownloadPlugin",
            "url_configs": [
                {
                    "config_name": "missing-basic",
                    "url_list": ["https://example\\.com/.*"],
                    "Basic-Auth": {
                        "username": None,
                        "password": None
                    }
                }
            ]
        }
        try:
            AuthDownloadPlugin.get_request_headers(
                missing_basic_config,
                missing_basic_config["url_configs"][0]
            )
            raise AssertionError("Expected missing-basic retrieval failure")
        except ValueError as e:
            if "Failed to retrieve basic auth credentials" not in str(e):
                raise

        missing_header_config = {
            "plugin_name": "AuthDownloadPlugin",
            "url_configs": [
                {
                    "config_name": "missing-header",
                    "url_list": ["https://example\\.com/.*"],
                    "Header": {
                        "X-Api-Key": None
                    }
                }
            ]
        }
        try:
            AuthDownloadPlugin.get_request_headers(
                missing_header_config,
                missing_header_config["url_configs"][0]
            )
            raise AssertionError("Expected missing-header retrieval failure")
        except ValueError as e:
            if "Failed to retrieve header value" not in str(e):
                raise

    _run_with_fake_keyring(_test)


def run_unit_tests() -> None:
    print("running auth/header unit tests")
    test_basic_auth_headers()
    test_custom_headers()
    test_basic_and_custom_headers()
    test_missing_keyring_values_failures()
    print("auth/header unit tests passed")


def run_integration_test() -> None:
    """Run existing end-to-end download test behavior."""
    # get absolute path to config file relative to the tests.py file location
    config_path_test = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test-config.json")
    with open(config_path_test, "r", encoding='utf-8') as f:
        config_json = json.load(f)

    # get the github credential from the ENV, will be populated in github action automatically.
    github_token = os.getenv('GITHUB_TOKEN', "testing")
    config_json["url_configs"][1]["Header"]["Authorization"] = f"token {github_token}"

    # put config file in root of repo:
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

    print(f"writing test config file {config_path}")
    with open(config_path, "w", encoding='utf-8') as f:
        json.dump(config_json, f, indent=2)

    print(f"script path: {AuthDownloadPlugin.get_script_path()}")

    print("run integration test")
    results = AuthDownloadPlugin.main(downloads="tests/test-downloads.json")

    print("cleanup test config files")
    os.remove(config_path)

    print("validate integration results.")
    print(results)
    for result in results:
        if not result["success"]:
            sys.exit(-1)

def main() -> None:
    """execution of tests starts here."""
    print("starting tests")
    run_unit_tests()
    run_integration_test()


if __name__ == "__main__":
    main()
