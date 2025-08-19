from service.config import API_TOKEN


def _get(client, path: str):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.get(path + (sep + f"token={token}" if token else ""))


def _post(client, path: str, json: dict):
    token = API_TOKEN or ""
    sep = "&" if "?" in path else "?"
    return client.post(path + (sep + f"token={token}" if token else ""), json=json)


def test_risk_overview_keys(client):
    resp = _get(client, "/risk/overview?strategy=dummy")
    assert resp.status_code == 200
    data = resp.json()
    for key in ["var95", "vol30d", "maxDrawdown", "beta30d", "alerts"]:
        assert key in data


def test_risk_rules_list(client):
    resp = _get(client, "/risk/rules")
    assert resp.status_code == 200
    assert "rules" in resp.json()


def test_risk_rule_validation(client):
    bad_metric = {
        "name": "x",
        "strategy": "s",
        "metric": "bogus",
        "operator": ">",
        "threshold": 1,
    }
    resp = _post(client, "/risk/rules", bad_metric)
    assert resp.status_code == 400
    bad_op = {**bad_metric, "metric": "var95", "operator": "??"}
    resp2 = _post(client, "/risk/rules", bad_op)
    assert resp2.status_code == 400
