import sys
import os
import time
from threading import Lock

from ftxwebsocket.client import FtxWebsocketClient
from ftxrest.client import FtxClient


if len(sys.argv) < 2:
    raise ValueError("Must specify a market")

MARKET = sys.argv[1]

last_printed_trade = None
ws_trades = []
print_lock = Lock()
rest_client = FtxClient(
    api_key="Doesnt matter, just using public APIs",
    api_secret="Doesnt matter, just using public APIs",
)


def _fetch_missing_trades_when_appropriate():
    last_trade = _get_last_ws_trade()

    with print_lock:
        while not _get_last_ws_trade() or _get_last_ws_trade() == last_trade:
            time.sleep(.1)

        _fetch_missing_trades()


def _get_ws_trades(ws_client):
    # Trades arrive in e.g. [[{T1}, {T2}, ...], [{T5}, {T6}, ...], ...] format,
    # so flatten them
    trade_lists = ws_client.get_trades(MARKET)
    return [trade for trade_sublist in trade_lists for trade in trade_sublist]


def _get_last_ws_trade():
    if not ws_trades:
        return None
    else:
        return ws_trades[-1]


def _get_trade_time(trade):
    from dateutil import parser
    return parser.parse(trade["time"])


def _sort_trades(trades):
    # Sort by time and then by ID in case of equivalent times
    sort_trade_key = lambda trade: (_get_trade_time(trade), int(trade["id"]))
    return sorted(trades, key=sort_trade_key)


def _fetch_missing_trades():
    # Subtract one to account for upward timestamp rounding due to fractional seconds
    start_time = int(_get_trade_time(last_printed_trade).timestamp()) - 1 if last_printed_trade else None
    end_time = int(time.time())
    trades_since_last = _sort_trades(rest_client.get_trades(market=MARKET, start_time=start_time, end_time=end_time))
    _print_new_trades(trades_since_last)


def _print_new_trades(trades):
    global last_printed_trade
    for trade in trades:
        if (
            last_printed_trade is None or
            (_get_trade_time(trade), int(trade["id"])) >
            (_get_trade_time(last_printed_trade), int(last_printed_trade["id"]))
        ):
            last_printed_trade = trade
            print(trade["time"], trade["id"])
            with open("trades.txt", "a") as f:
                f.write(f'{trade["time"]} {trade["id"]}\n')


def _new_ws_client():
    return FtxWebsocketClient(on_disconnect=_fetch_missing_trades_when_appropriate)

if os.path.exists("trades.txt"):
    os.remove("trades.txt")

ws_client = _new_ws_client()
while True:
    if ws_client.lost_connection:
        ws_client = _new_ws_client()
    ws_trades = _sort_trades(_get_ws_trades(ws_client))

    acquired_print_lock = False
    try:
        if print_lock.acquire(timeout=1):
            acquired_print_lock = True
            _print_new_trades(ws_trades)
    finally:
        if acquired_print_lock:
            print_lock.release()

    time.sleep(.1)
