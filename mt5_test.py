import MetaTrader5 as mt5
import sys

mt5.shutdown()
print("Attempting connection to C:/MT5 with new account...")

if mt5.initialize(
    path=r"C:/MT5/terminal64.exe",
    login=115262282,
    password="_1fsHbFl",
    server="MetaQuotes-Demo",
    portable=True,
    timeout=60000
):
    print("CONNECTED SUCCESSFULLY!")
    info = mt5.account_info()
    print("Account:", info.login)
    print("Balance:", info.balance, info.currency)
    
    rates = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_H1, 0, 3)
    if rates is not None and len(rates) > 0:
        print("\nEURUSD H1 Candles:")
        for r in rates:
            print(dict(r))
    else:
        print("No candles. Error:", mt5.last_error())
    
    mt5.shutdown()
    print("Done.")
else:
    print("initialize() failed:", mt5.last_error())
    sys.exit(1)
