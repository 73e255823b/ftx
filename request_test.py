import requests

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [0.5, 0.5])),
        "markets": ",".join(["ETH-PERP", "BTC-PERP"]),
    }
)
assert resp.status_code == 200

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [0.5, 0.25, 0.25])),
        "markets": ",".join(["ETH-PERP", "BTC-PERP", "BTC/USD"]),
    }
)
assert resp.status_code == 200

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [0.1])),
        "markets": ",".join(["ETH-PERP", "BTC-PERP"]),
    }
)
assert resp.status_code == 400
"Mismatched lengths" in resp.text

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [-0.5, 1.5])),
        "markets": ",".join(["ETH-PERP", "BTC-PERP"]),
    }
)
assert resp.status_code == 400
"Weights cannot be negative" in resp.text

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": "foo,bar",
        "markets": ",".join(["ETH-PERP", "BTC-PERP"]),
    }
)
assert resp.status_code == 400
"Weights cannot be negative" in resp.text

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [0.1, 0.1])),
        "markets": ",".join(["ETH-PERP", "BTC-PERP"]),
    }
)
assert resp.status_code == 400
"Weights must sum to 1" in resp.text

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [1])),
        "markets": ",".join(["LUNA-PERP"]),
    }
)
assert resp.status_code == 400
assert "unrecognized market" in resp.text

resp = requests.get(
    url="http://127.0.0.1:5000/index",
    params={
        "weights": ",".join(map(str, [0.5, 0.5])),
        "markets": ",".join(["LUNA-PERP", "LUNA-PERP"]),
    }
)
assert resp.status_code == 400
assert "markets is duplicated" in resp.text

print("Passed!")
