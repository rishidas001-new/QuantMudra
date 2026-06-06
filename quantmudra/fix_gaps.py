#!/usr/bin/env python3
"""Fix remaining data gaps for stocks starting Jan 2016"""
import yfinance as yf
import pandas as pd
import oracledb

DB = {
    'user': 'admin', 'password': 'QuantMudra@2026', 'dsn': 'quantmudra_high',
    'wallet_location': '/home/openhands/.oci/quantmudra_wallet', 
    'wallet_password': 'QuantMudra@2026'
}

def connect():
    return oracledb.connect(
        user=DB['user'], password=DB['password'], dsn=DB['dsn'],
        config_dir=DB['wallet_location'], wallet_location=DB['wallet_location'],
        wallet_password=DB['wallet_password']
    )

# 43 stocks with gaps
gaps = [
    ('NH.NS', 3), ('CIEINDIA.NS', 2), ('AEGISLOG.NS', 2), ('HONAUT.NS', 2),
    ('3MINDIA.NS', 2), ('AIAENG.NS', 2), ('PAGEIND.NS', 2), ('PHOENIXLTD.NS', 2),
    ('THERMAX.NS', 1), ('OBEROIRLTY.NS', 1), ('PVRINOX.NS', 1), ('SOLARINDS.NS', 1),
    ('IPCALAB.NS', 1), ('MINDACORP.NS', 1), ('SIEMENS.NS', 1), ('ALKEM.NS', 1),
    ('GALLANTT.NS', 1), ('SAREGAMA.NS', 1), ('MRF.NS', 1), ('GRANULES.NS', 1),
    ('LINDEINDIA.NS', 1), ('NAVINFLUOR.NS', 1), ('RAMCOCEM.NS', 1), ('TIMKEN.NS', 1),
    ('AUROPHARMA.NS', 1), ('BHARATFORG.NS', 1), ('RHIM.NS', 1), ('EIDPARRY.NS', 1),
    ('AJANTPHARM.NS', 1), ('BALKRISIND.NS', 1), ('CARBORUNIV.NS', 1), ('DIVISLAB.NS', 1),
    ('KPIL.NS', 1), ('PFIZER.NS', 1), ('JUBLPHARMA.NS', 1), ('SOBHA.NS', 1),
    ('RADICO.NS', 1), ('KIRLOSENG.NS', 1), ('DEEPAKNTR.NS', 1), ('DCMSHRIRAM.NS', 1),
    ('CAPLIPOINT.NS', 1), ('BOSCHLTD.NS', 1), ('INDIGO.NS', 1)
]

print("="*70)
print("FIXING REMAINING DATA GAPS")
print("="*70)
print(f"Total: {len(gaps)} stocks, {sum(g[1] for g in gaps)} missing records")

total_fixed = 0

for sym, missing_count in gaps:
    print(f"\n{sym} ({missing_count} missing)...", end=" ")
    
    try:
        conn = connect()
        cursor = conn.cursor()
        
        # Get existing dates
        cursor.execute("""
            SELECT trade_date FROM admin.stock_ohlcv_daily 
            WHERE symbol=:1 AND trade_date >= DATE '2016-01-01'
        """, [sym])
        existing = set([row[0] for row in cursor.fetchall()])
        
        # Download 2016-2026 data
        df = yf.download(sym, start='2016-01-01', end='2026-06-06',
                        interval="1d", auto_adjust=False, progress=False, timeout=30)
        
        if df.empty:
            print("⚠️ No data")
            cursor.close()
            conn.close()
            continue
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        
        df = df.reset_index()
        df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
        
        # Find missing dates
        missing_rows = []
        for _, row in df.iterrows():
            dt = row['Date'].date()
            if dt not in existing:
                missing_rows.append({
                    'sym': sym, 'dt': dt,
                    'open': float(row['Open']), 'high': float(row['High']),
                    'low': float(row['Low']), 'close': float(row['Close']),
                    'adj': float(row['Adj Close']), 'vol': int(row['Volume']),
                    'nse': f"NSE:{sym.replace('.NS','')}-EQ"
                })
        
        if missing_rows:
            cursor.executemany("""
                MERGE INTO admin.stock_ohlcv_daily t
                USING (SELECT :sym as symbol, :dt as trade_date FROM dual) s
                ON (t.symbol = s.symbol AND t.trade_date = s.trade_date)
                WHEN NOT MATCHED THEN INSERT 
                    (symbol,trade_date,open_price,high_price,low_price,close_price,adj_close,volume,nse_symbol)
                VALUES (:sym,:dt,:open,:high,:low,:close,:adj,:vol,:nse)
            """, missing_rows)
            conn.commit()
            print(f"✅ +{len(missing_rows)}")
            total_fixed += len(missing_rows)
        else:
            print("✓ (no gap)")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ {str(e)[:40]}")

print("\n" + "="*70)
print(f"✅ TOTAL FIXED: {total_fixed} records")
print("="*70)
