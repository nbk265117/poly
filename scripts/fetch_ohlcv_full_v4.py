#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ohlcv_full_v4.py - Télécharge des données OHLCV 1m depuis Binance
Version 4.0 - Support des paires complètes (ex: ETH/BTC)

- Paires par défaut: BTC/USDT, ETH/USDT, ETH/BTC
- Support des formats: "BTC" (assume /USDT) ou "ETH/BTC" (paire complète)
- Ajoute/merge au CSV existant si présent (resume automatique)
- Calcule quote_volume = volume_base * close
- Détecte et signale les gaps dans les données
- Retry automatique en cas d'erreur réseau
- Sortie: ohlcv_top10/{BASE}_{QUOTE}.csv

Dépendances: pip install ccxt pandas numpy
"""
import os
import time
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
import argparse

import ccxt
import pandas as pd
import numpy as np

UTC = timezone.utc

# Maintenant on peut spécifier des paires complètes ou juste des bases
SYMBOLS_DEFAULT = ["BTC/USDT", "ETH/USDT", "ETH/BTC"]

def ms(dt: datetime) -> int:
    """Convert datetime to milliseconds"""
    return int(dt.timestamp() * 1000)

def iso(ts_ms: int) -> str:
    """Convert milliseconds to ISO string"""
    return datetime.fromtimestamp(ts_ms/1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S%z")

def ensure_dir(p: str):
    """Create directory if it doesn't exist"""
    os.makedirs(p, exist_ok=True)

def parse_symbol(symbol: str, default_quote: str = "USDT") -> Tuple[str, str]:
    """Parse a symbol string into base and quote currencies
    
    Examples:
        "BTC" -> ("BTC", "USDT")
        "ETH/BTC" -> ("ETH", "BTC")
        "SOL/USDT" -> ("SOL", "USDT")
    """
    if "/" in symbol:
        parts = symbol.split("/")
        return parts[0].upper(), parts[1].upper()
    else:
        return symbol.upper(), default_quote.upper()

def merge_save_csv(path: str, df_new: pd.DataFrame):
    """Merge new data with existing CSV and save"""
    # Harmoniser timestamps en UTC (tz-aware)
    df_new = df_new.copy()
    df_new["timestamp"] = pd.to_datetime(df_new["timestamp"], utc=True, errors="coerce")

    # Ajoute/merge avec l'existant si présent
    if os.path.exists(path):
        try:
            df_old = pd.read_csv(path, parse_dates=["timestamp"])
            # Force UTC (évite mélange tz-naive/aware)
            df_old["timestamp"] = pd.to_datetime(df_old["timestamp"], utc=True, errors="coerce")
        except Exception:
            df_old = pd.DataFrame()
    else:
        df_old = pd.DataFrame()

    if not df_old.empty:
        combined = pd.concat([
            df_old.set_index("timestamp"),
            df_new.set_index("timestamp")
        ], axis=0)
    else:
        combined = df_new.set_index("timestamp")

    # Dédoublonner & trier
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()

    # Triage colonnes et dtypes
    for col in ["open","high","low","close","volume","quote_volume"]:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").astype(float)
    
    combined = combined.reset_index()
    combined.to_csv(path, index=False)
    return combined

def check_gaps(df: pd.DataFrame, timeframe_minutes: int = 1):
    """Vérifie et affiche les gaps dans les données"""
    if len(df) <= 1:
        return
    
    df_sorted = df.sort_values("timestamp")
    time_diffs = df_sorted["timestamp"].diff()
    expected_diff = pd.Timedelta(minutes=timeframe_minutes)
    
    # Gaps = différences > 150% du temps attendu
    gaps = time_diffs[time_diffs > expected_diff * 1.5]
    
    if len(gaps) > 0:
        print(f"⚠️  {len(gaps)} gap(s) detected in data:")
        for idx in gaps.index[:10]:  # Afficher max 10 premiers gaps
            gap_start = df_sorted.loc[idx - 1, "timestamp"]
            gap_end = df_sorted.loc[idx, "timestamp"]
            gap_duration = time_diffs.loc[idx]
            print(f"  Gap: {gap_start} → {gap_end} (duration: {gap_duration})")
        
        if len(gaps) > 10:
            print(f"  ... and {len(gaps) - 10} more gaps")

def fetch_symbol(exchange: ccxt.Exchange, base: str, quote: str, months: int, 
                 timeframe: str, out_dir: str):
    """Télécharge les données OHLCV pour un symbole"""
    
    symbol = f"{base}/{quote}"
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    tf_minutes = tf_ms // 60000

    now_ms = ms(datetime.now(tz=UTC))
    since_ms = ms(datetime.now(tz=UTC) - timedelta(days=months*30))

    # Resume: si un CSV existe, on repart de la dernière bougie + 1 tf
    # Nom du fichier adapté pour supporter différentes quotes
    out_path = os.path.join(out_dir, f"{base}_{quote}.csv")
    if os.path.exists(out_path):
        try:
            tmp = pd.read_csv(out_path, usecols=["timestamp"], parse_dates=["timestamp"])
            # Force UTC pour être 100% tz-aware
            tmp["timestamp"] = pd.to_datetime(tmp["timestamp"], utc=True, errors="coerce")
            if not tmp.empty:
                last_ts_ms = int(tmp["timestamp"].max().timestamp() * 1000)
                since_ms = max(since_ms, last_ts_ms + tf_ms)
                print(f"📂 Resuming from {iso(since_ms)}")
        except Exception as e:
            print(f"⚠️  Could not read existing file: {e}")

    print(f"\n{'='*80}")
    print(f"📊 {symbol} - downloading from {iso(since_ms)} to {iso(now_ms)}")
    print(f"   Period: {months} months | Timeframe: {timeframe}")
    print(f"{'='*80}")

    all_rows = []
    last_print = time.time()
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while True:
        try:
            ohlcvs = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since_ms, limit=1000)
            consecutive_errors = 0  # Reset on success
            
        except ccxt.RateLimitExceeded:
            print("⏳ Rate limit exceeded, waiting...")
            time.sleep(exchange.rateLimit/1000.0 + 1.0)
            continue
            
        except ccxt.NetworkError as e:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                print(f"❌ Too many network errors ({max_consecutive_errors}), aborting")
                break
            wait_time = min(2 ** consecutive_errors, 30)  # Exponential backoff, max 30s
            print(f"⚠️  Network error ({consecutive_errors}/{max_consecutive_errors}): {e}")
            print(f"   Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue
            
        except Exception as e:
            consecutive_errors += 1
            if consecutive_errors >= max_consecutive_errors:
                print(f"❌ Too many errors ({max_consecutive_errors}), aborting: {e}")
                break
            wait_time = min(2 ** consecutive_errors, 30)
            print(f"⚠️  Error ({consecutive_errors}/{max_consecutive_errors}): {e}")
            print(f"   Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue

        if not ohlcvs:
            break

        all_rows.extend(ohlcvs)
        since_ms = ohlcvs[-1][0] + tf_ms

        # Progress print
        if time.time() - last_print > 2.0:
            print(f"  🔥 Downloaded ~{len(all_rows):,} rows, up to {iso(ohlcvs[-1][0])}")
            last_print = time.time()

        if since_ms >= now_ms:
            break
        
        time.sleep(exchange.rateLimit/1000.0 + 0.05)

    if not all_rows:
        print("ℹ️  No new data to fetch (already up to date)")
        return

    print(f"✅ Downloaded {len(all_rows):,} raw rows")

    # Build DataFrame
    df = pd.DataFrame(all_rows, columns=["ms","open","high","low","close","volume"])
    df["timestamp"] = pd.to_datetime(df["ms"], unit="ms", utc=True)
    df = df.drop(columns=["ms"])

    # Casts & quote_volume
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df["quote_volume"] = (df["volume"] * df["close"]).astype(float)

    # Dedup/sort
    df = df.dropna(subset=["timestamp"]).drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    print(f"✅ After dedup: {len(df):,} unique rows")

    # Check for gaps
    check_gaps(df, tf_minutes)

    # Merge & save (UTC strict)
    ensure_dir(out_dir)
    combined = merge_save_csv(out_path, df)
    
    print(f"{'='*80}")
    print(f"✅ {symbol} saved to {out_path}")
    print(f"   Total rows in file: {len(combined):,}")
    print(f"   Period: {combined['timestamp'].min()} to {combined['timestamp'].max()}")
    print(f"{'='*80}\n")

def main():
    ap = argparse.ArgumentParser(
        description="Download OHLCV data from Binance with support for custom pairs"
    )
    ap.add_argument("--symbols", type=str, default=",".join(SYMBOLS_DEFAULT), 
                    help=f"Comma-separated list of symbols. Can be 'BTC' (assumes USDT) or 'ETH/BTC' (full pair). Default: {','.join(SYMBOLS_DEFAULT)}")
    ap.add_argument("--quote", type=str, default="USDT",
                    help="Default quote currency for symbols without '/' (default: USDT)")
    ap.add_argument("--months", type=int, default=48,
                    help="Number of months to download (default: 48)")
    ap.add_argument("--timeframe", type=str, default="1m",
                    help="Timeframe (default: 1m)")
    ap.add_argument("--out-dir", type=str, default="ohlcv_top10",
                    help="Output directory (default: ohlcv_top10)")
    ap.add_argument("--api-key", type=str, default=None,
                    help="Binance API key (optional)")
    ap.add_argument("--api-secret", type=str, default=None,
                    help="Binance API secret (optional)")
    args = ap.parse_args()

    print("\n" + "="*80)
    print("📊 BINANCE OHLCV DOWNLOADER v4.0")
    print("="*80)

    exchange = ccxt.binance({
        "enableRateLimit": True,
        "apiKey": args.api_key or "",
        "secret": args.api_secret or "",
        "options": {"defaultType": "spot"},
    })

    # Parse symbols
    symbols_raw = [s.strip() for s in args.symbols.split(",") if s.strip()]
    pairs = []
    
    for sym in symbols_raw:
        base, quote = parse_symbol(sym, args.quote)
        pairs.append((base, quote))
    
    print(f"Pairs to download: {', '.join([f'{b}/{q}' for b, q in pairs])}")
    print(f"Default quote (for simple symbols): {args.quote}")
    print(f"Timeframe: {args.timeframe}")
    print(f"Period: {args.months} months")
    print(f"Output directory: {args.out_dir}")
    print()

    for i, (base, quote) in enumerate(pairs, 1):
        print(f"[{i}/{len(pairs)}] Processing {base}/{quote}...")
        try:
            fetch_symbol(exchange, base, quote, args.months, 
                        args.timeframe, args.out_dir)
        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to process {base}/{quote}: {e}")
            continue

    print("\n" + "="*80)
    print("✅ All pairs processed")
    print("="*80)

if __name__ == "__main__":
    main()
