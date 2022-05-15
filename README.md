1. Run ``python market.py BTC-PERP``.
2. Observe that trade IDs and timestamps are printed to stdout.
3. Simulate websocket disconnection by disabling internet connection
4. Reenable internet connection
5. Observe that trade ID and timestamp printing resumes, with missed trades fetched via REST API request and printed prior to new websocket trades.
6. The ``market.py`` scrpt writes trades to a ``trades.txt`` file. Run ``python test.py BTC-PERP``, which reads trades from the file and compares them with trades fetched from the FTX REST API during that time, to verify that all expected records are present.
