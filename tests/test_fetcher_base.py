"""Tests de BaseFetcher (lógica pura, sin BD)."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from stonks.fetchers.base import BaseFetcher


class DummyFetcher(BaseFetcher):
    SOURCE_NAME = "test"
    DOMAIN = "test"
    RATE_LIMIT = 0.1
    MAX_RETRIES = 2


def test_rate_limit_espera():
    f = DummyFetcher()
    f._last_request = time.time()
    t0 = time.time()
    f._rate_limit()
    elapsed = time.time() - t0
    assert elapsed >= 0.05


def test_rate_limit_no_espera_si_ya_paso():
    f = DummyFetcher()
    f._last_request = time.time() - 1.0
    t0 = time.time()
    f._rate_limit()
    elapsed = time.time() - t0
    assert elapsed < 0.05


@patch.object(BaseFetcher, "_rate_limit")
def test_get_retorna_json(mock_rl):
    f = DummyFetcher()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True}
    mock_resp.raise_for_status = MagicMock()
    f._session.get = MagicMock(return_value=mock_resp)

    result = f._get("http://example.com/api")
    assert result == {"ok": True}
    f._session.get.assert_called_once()


@patch.object(BaseFetcher, "_rate_limit")
def test_get_reintenta_en_error(mock_rl):
    f = DummyFetcher()

    mock_fail = MagicMock()
    mock_fail.raise_for_status.side_effect = requests.RequestException(
        "timeout"
    )

    mock_ok = MagicMock()
    mock_ok.json.return_value = {"retry": True}
    mock_ok.raise_for_status = MagicMock()

    f._session.get = MagicMock(side_effect=[mock_fail, mock_ok])

    with patch("time.sleep"):
        result = f._get("http://example.com/api")

    assert result == {"retry": True}
    assert f._session.get.call_count == 2


@patch.object(BaseFetcher, "_rate_limit")
def test_get_falla_tras_reintentos(mock_rl):
    f = DummyFetcher()

    mock_fail = MagicMock()
    mock_fail.raise_for_status.side_effect = requests.RequestException("down")

    f._session.get = MagicMock(return_value=mock_fail)

    with (
        patch("time.sleep"),
        pytest.raises(requests.RequestException),
    ):
        f._get("http://example.com/api")

    assert f._session.get.call_count == 2


def test_state_roundtrip(tmp_path):
    f = DummyFetcher()
    with patch.object(
        f,
        "_state_path",
        return_value=tmp_path / "test_state.json",
    ):
        f._save_state("k", {"cursor": 42})
        loaded = f._load_state("k")
    assert loaded == {"cursor": 42}


def test_load_state_vacio(tmp_path):
    f = DummyFetcher()
    with patch.object(
        f,
        "_state_path",
        return_value=tmp_path / "no_existe.json",
    ):
        assert f._load_state("k") == {}
