import sys
from dateutil import parser

from ftxrest.client import FtxClient


if len(sys.argv) < 2:
    raise ValueError("Must specify a market")

MARKET = sys.argv[1]


rest_client = FtxClient(
    api_key="9e_zQ3DiCkiawmptnPZa4jC2IfFwMd3MRvQ4UI06",
    api_secret="4gzrFbrTMzCrZOkHdj6bj4ry2-A5QpS4aT1RZAC1",
)


def _get_trade_time(trade):
    return parser.parse(trade["time"])

def _sort_trades(trades):
    # Sort by time and then by ID in case of equivalent times
    sort_trade_key = lambda trade: (_get_trade_time(trade), trade["id"])
    return sorted(trades, key=sort_trade_key)


with open(f"{MARKET.replace('/', '-')}.txt", "r") as f:
    lines = f.readlines()

trades_from_file = []
for line in lines:
    trade_time, trade_id = line.rstrip("\n").split(" ")
    trade_from_file = {
        "time": trade_time,
        "id": int(trade_id),
    }
    trades_from_file.append(trade_from_file)

start_time = int(parser.parse(lines[0].split(" ")[0]).timestamp()) - 1
end_time = int(parser.parse(lines[-1].split(" ")[0]).timestamp()) + 1

trades_from_ftx_rest_api = rest_client.get_trades(market=MARKET, start_time=start_time, end_time=end_time)
trades_from_ftx_rest_api = _sort_trades(trades_from_ftx_rest_api)
trades_from_ftx_rest_api = [
    trade for trade in trades_from_ftx_rest_api
    if _get_trade_time(trade) >= _get_trade_time(trades_from_file[0])
    and _get_trade_time(trade) <= _get_trade_time(trades_from_file[-1])
]

assert len(trades_from_file) == len(trades_from_ftx_rest_api), f"{len(trades_from_file)}, {len(trades_from_ftx_rest_api)}"
for i in range(len(trades_from_file)):
    file_trade = trades_from_file[i]
    ftx_trade = trades_from_ftx_rest_api[i]
    assert file_trade["id"] == ftx_trade["id"], f"{file_trade}, {ftx_trade}"

print(f"PASSED! Validated {len(trades_from_file)} records")
