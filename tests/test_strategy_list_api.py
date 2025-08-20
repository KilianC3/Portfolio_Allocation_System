from service.config import API_TOKEN
import strategies


def _get(client, path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def test_strategy_list_includes_package(client):
    resp = _get(client, "/strategies")
    assert resp.status_code == 200
    data = resp.json()["strategies"]
    for name in strategies.__all__:
        assert name in data
