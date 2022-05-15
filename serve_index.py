import sys
import os
import time
import statistics
from multiprocessing import Process, Manager
from threading import Thread, Lock

from flask import Flask
from flask import request

from ftxwebsocket.client import FtxWebsocketClient
from ftxrest.client import FtxClient


class TradeUpdateStreamer:

    def __init__(self, market, latest_trades_by_market):
        self.market = market
        self.market_file_name = f"{self.market.replace('/', '-')}.txt"
        self.last_printed_trade = None
        self.latest_trades_by_market = latest_trades_by_market
        self.ws_trades = []
        self.print_lock = Lock()
        self.rest_client = FtxClient(
            api_key="Doesnt matter, just using public APIs",
            api_secret="Doesnt matter, just using public APIs",
        )

        if os.path.exists(self.market_file_name):
            os.remove(self.market_file_name)

    def _fetch_missing_trades_when_appropriate(self):
        last_trade = self._get_last_ws_trade()

        with self.print_lock:
            while not self._get_last_ws_trade() or self._get_last_ws_trade() == last_trade:
                time.sleep(.1)

            self._fetch_missing_trades()

    def _get_ws_trades(self, ws_client):
        trade_lists = ws_client.get_trades(self.market)
        # Trades arrive in e.g. [[{T1}, {T2}, ...], [{T5}, {T6}, ...], ...] format,
        # so flatten them
        return [trade for trade_sublist in trade_lists for trade in trade_sublist]

    def _get_last_ws_trade(self):
        if not self.ws_trades:
            return None
        else:
            return self.ws_trades[-1]

    def _get_trade_time(self, trade):
        from dateutil import parser
        return parser.parse(trade["time"])

    def _sort_trades(self, trades):
        # Sort by time and then by ID in case of equivalent times
        sort_trade_key = lambda trade: (self._get_trade_time(trade), int(trade["id"]))
        return sorted(trades, key=sort_trade_key)

    def _fetch_missing_trades(self):
        # Subtract one to account for upward timestamp rounding due to fractional seconds
        start_time = int(self._get_trade_time(self.last_printed_trade).timestamp()) - 1 if self.last_printed_trade else None
        end_time = int(time.time())
        trades_since_last = self._sort_trades(self.rest_client.get_trades(market=self.market, start_time=start_time, end_time=end_time))
        self._print_new_trades(trades_since_last)

    def _print_new_trades(self, trades):
        for trade in trades:
            if (
                self.last_printed_trade is None or
                (self._get_trade_time(trade), int(trade["id"])) >
                (self._get_trade_time(self.last_printed_trade), int(self.last_printed_trade["id"]))
            ):
                self.latest_trades_by_market[self.market] = trade
                self.last_printed_trade = trade
                # Write the latest trade to a file for testing
                with open(self.market_file_name, "a") as f:
                    f.write(f'{trade["time"]} {trade["id"]}\n')

    def _new_ws_client(self):
        return FtxWebsocketClient(on_disconnect=self._fetch_missing_trades_when_appropriate)

    def start(self):
        ws_client = self._new_ws_client()
        while True:
            if ws_client.lost_connection:
                ws_client = self._new_ws_client()
            self.ws_trades = self._sort_trades(self._get_ws_trades(ws_client))

            acquired_print_lock = False
            try:
                if self.print_lock.acquire(timeout=1):
                    acquired_print_lock = True
                    self._print_new_trades(self.ws_trades)
            finally:
                if acquired_print_lock:
                    self.print_lock.release()

            time.sleep(.1)


def stream_trades(market, latest_trades_by_market):
    streamer = TradeUpdateStreamer(market, latest_trades_by_market)
    streamer.start()


def get_weighted_index_price(latest_trades_by_market, markets, weights):
    ONE_BP = 0.0001
    prices_ordered_by_market = [latest_trades_by_market[market]["price"] for market in markets]
    median_price = statistics.median(prices_ordered_by_market)
    min_price_for_index_average = median_price - (30 * ONE_BP * median_price)
    max_price_for_index_average = median_price + (30 * ONE_BP * median_price)
    prices_for_index_average = [
        # Cap each element of the weighted average at 30 basis points from the median
        min(max(price, min_price_for_index_average), max_price_for_index_average)
        for price in prices_ordered_by_market
    ]
    index_price = 0
    for price, weight in zip(prices_for_index_average, weights):
        index_price += (price * weight)

    return str(index_price)

    # For testing
    # return {
    #     "index_price": str(index_price),
    #     "prices_for_avg": prices_for_index_average,
    #     "median_price": median_price,
    #     "min_price_for_index_average": min_price_for_index_average,
    #     "max_price_for_index_average": max_price_for_index_average,
    # }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("Must specify the path to an input file containing all markets to track")

    markets_path = sys.argv[1]
    with open(markets_path, "r") as f:
        configured_markets = set([line.rstrip("\n") for line in f.readlines()])

    latest_trades_by_market = Manager().dict()
    for market in configured_markets:
        stream_proc = Process(target=stream_trades, args=(market, latest_trades_by_market,))
        stream_proc.start()

    app = Flask(__name__)

    @app.route("/index")
    def index():
        # if "markets" not in request.args or "weights" not in request.args:
        markets = request.args.get("markets")
        weights = request.args.get("weights")
        if not markets or not weights:
            return "Must specify commma separated lists of `markets` and `weights` as query parameters", 400

        try:
            markets = markets.split(",")
            weights = [float(weight_str) for weight_str in weights.split(",")]
        except Exception:
            return "Invalid markets and or weights", 400

        if any([weight < 0 for weight in weights]):
            return "Weights cannot be negative", 400

        # TODO: Do weights above or below 1 make sense? Maybe...
        if sum(weights) != 1:
            return "Weights must sum to 1", 400

        if len(set(markets)) != len(markets):
            return "One or more requested markets is duplicated", 400

        if len(markets) != len(weights):
            return "Mismatched lengths of markets and weights", 400

        if not set(markets) <= configured_markets:
            return "One or more unrecognized markets", 400

        # TODO: Consider a timeout
        while True:
            trades_by_market_snapshot = dict(latest_trades_by_market)
            if not set(markets) <= trades_by_market_snapshot.keys():
                # NB: If a request arrives shortly after server start, the
                # server may not have yet fetched data for the specified
                # markets. Accordingly, we await such data; an alternative
                # would be to fail the request, but this seems friendlier
                # (if we fail, clients need to implement their own retry
                # loop to handle this case)
                time.sleep(.5)
            else:
                return get_weighted_index_price(
                    latest_trades_by_market=trades_by_market_snapshot,
                    markets=markets,
                    weights=weights,
                )

    app.run(host="127.0.0.1", port=5000)
