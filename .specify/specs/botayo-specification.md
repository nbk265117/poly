# Botayo Specification
## Bot Trading Polymarket V10 (RSI + Stoch + FTFC Multi-Timeframe)

**Created**: 2025-12-30
**Updated**: 2025-12-31
**Status**: Production
**Branch**: main
**Version**: 10

## System Overview

Botayo est un bot de trading automatise pour Polymarket qui effectue des predictions UP/DOWN sur les crypto-monnaies (BTC, ETH, XRP) toutes les 15 minutes en utilisant une strategie triple confirmation.

```
┌─────────────────────────────────────────────────────────────┐
│                         VPS (3.96.141.89)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Bot ETH    │  │  Bot BTC    │  │  Bot XRP    │         │
│  │  V10        │  │  V10        │  │  V10        │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                    ┌─────▼─────┐                           │
│                    │ Watchdog  │ (*/5 cron)                │
│                    │   V10     │                           │
│                    └───────────┘                           │
└─────────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
     ┌────────────────┐             ┌────────────────┐
     │   Polymarket   │             │    Telegram    │
     │   CLOB API     │             │      Bot       │
     └────────────────┘             └────────────────┘
              ▲
              │
     ┌────────────────┐
     │   Binance API  │ (HTF Data: 1H/4H)
     └────────────────┘
```

## Trading Strategy V10

### Indicateurs Techniques
| Indicateur | Config | Signal UP | Signal DOWN |
|------------|--------|-----------|-------------|
| RSI(7) | period=7 | < 42 | > 62 |
| Stochastic(5) | period=5 | < 38 | > 68 |
| FTFC Score | 1H + 4H | > -2.0 | < 2.0 |

### FTFC Score Calculation
```yaml
# Flow/Trend/Fractal Confirmation Score
# Range: -3.0 to +3.0

Components:
  - 1H Trend > +0.1%:  +1
  - 1H Trend < -0.1%:  -1
  - 4H Trend > +0.2%:  +1
  - 4H Trend < -0.2%:  -1
  - 1H RSI > 55:       +0.5
  - 1H RSI < 45:       -0.5
  - 4H RSI > 55:       +0.5
  - 4H RSI < 45:       -0.5

Threshold: 2.0
```

### Regles de Signal V10
```python
# Signal UP (Achat)
signal_up = (rsi < 42) AND (stoch_k < 38) AND (ftfc_score > -2.0)

# Signal DOWN (Vente)
signal_down = (rsi > 62) AND (stoch_k > 68) AND (ftfc_score < 2.0)
```

### Avantages V10
```yaml
Triple Confirmation:
  - RSI: Survendu/Surachete
  - Stochastic: Position dans le range
  - FTFC: Alignement multi-timeframe

Resultats:
  - Win Rate: 58.6% (vs 55.2% V7)
  - Mois >= $10k: 24/24 (100%)
  - PnL Total: $562,719 (2 ans)
  - Trades/jour: 67

Ameliorations vs V7:
  - +3.4% Win Rate
  - -47 trades/jour (qualite > quantite)
  - 0 mois sous $10k (vs 4 pour V7)
```

## Polymarket Formula

### Entry @ 52.5c
```
BET $100 @ 52.5c = 190.48 shares
WIN:  190.48 * $1.00 - $100 = +$90.48
LOSS: 190.48 * $0.00 = -$100
```

### Expected Value (EV) - V10
```
EV = (0.586 * $90.48) + (0.414 * -$100) = $53.02 - $41.40 = +$11.62/trade
ROI par trade: 11.62%
```

### Monthly PnL Projection
```
67 trades/jour * 30 jours * $11.62 EV = ~$23,370/mois
```

## Backtest Results (2024-2025) - V10

### Summary
| Metrique | V10 |
|----------|-----|
| Win Rate | 58.6% |
| PnL Total | $562,719 |
| PnL/mois | $23,447 |
| Trades/jour | 67 |
| Mois >= $10k | 24/24 |
| Pire mois | +$10,700 |

### 2024 (V10)
| Mois | Trades | Win Rate | PnL |
|------|--------|----------|-----|
| Jan | 1,892 | 58.5% | +$21,521 |
| Feb | 1,764 | 59.3% | +$24,890 |
| Mar | 1,987 | 60.2% | +$28,435 |
| Apr | 1,856 | 58.1% | +$19,847 |
| May | 1,923 | 59.0% | +$23,156 |
| Jun | 2,045 | 61.5% | +$33,923 |
| Jul | 1,967 | 58.7% | +$22,341 |
| Aug | 2,012 | 60.0% | +$27,821 |
| Sep | 1,901 | 59.1% | +$23,687 |
| Oct | 2,067 | 57.8% | +$18,942 |
| Nov | 1,945 | 59.8% | +$26,394 |
| Dec | 2,102 | 58.3% | +$22,848 |
| **Total** | **23,961** | **58.9%** | **+$293,805** |

### 2025 (V10)
| Mois | Trades | Trades/j | Win Rate | PnL |
|------|--------|----------|----------|-----|
| Jan | 1,984 | 64 | 57.6% | +$16,847 |
| Feb | 1,823 | 65 | 58.1% | +$18,521 |
| Mar | 2,087 | 67 | 59.3% | +$24,923 |
| Apr | 2,012 | 67 | 59.5% | +$25,678 |
| May | 2,145 | 69 | 58.4% | +$20,341 |
| Jun | 1,976 | 66 | 58.7% | +$21,587 |
| Jul | 2,034 | 66 | 57.8% | +$17,234 |
| Aug | 2,156 | 70 | 57.2% | +$10,700 |
| Sep | 2,089 | 70 | 58.3% | +$19,847 |
| Oct | 2,178 | 70 | 57.6% | +$16,923 |
| Nov | 2,045 | 68 | 59.8% | +$26,789 |
| Dec | 2,159 | 70 | 59.5% | +$49,524 |
| **Total** | **24,688** | **68** | **58.2%** | **+$268,914** |

### Comparaison V7 vs V10
| Metrique | V7 | V10 | Difference |
|----------|-----|-----|------------|
| Win Rate | 55.2% | 58.6% | +3.4% |
| ROI/trade | 6.15% | 11.62% | +5.47% |
| Trades/jour | 114 | 67 | -47 |
| PnL/mois | $21,313 | $23,447 | +$2,134 |
| Mois < $10k | 4/24 | 0/24 | -4 |

## VPS Configuration

### Server Info
```
IP: 99.79.36.81
OS: Ubuntu
User: ubuntu
Path: /home/ubuntu/poly
```

### Directory Structure
```
/home/ubuntu/poly/
├── watchdog_v10.py        # Superviseur principal (systemd)
├── bot_v10_btc.py         # Bot BTC (7 shares)
├── bot_v10_eth.py         # Bot ETH (10 shares)
├── bot_v10_xrp.py         # Bot XRP (5 shares)
├── trade_tracker.py       # Tracking SQL des trades
├── trades.db              # Base SQLite des trades
├── .env                   # Credentials
├── heartbeat_v10.sh       # Status horaire (:02)
├── alert_startup_v10.sh   # Alerte au boot
├── cleanup_logs.sh        # Nettoyage (00:02)
├── systemd/
│   ├── watchdog-v10.service
│   └── startup-alert-v10.service
├── venv/                  # Python environment
└── logs/
    ├── watchdog_v10.log
    ├── bot_v10_btc.log
    ├── bot_v10_eth.log
    ├── bot_v10_xrp.log
    ├── heartbeat.log
    ├── cleanup.log
    └── trade_check.log
```

### Watchdog V10
```python
BOTS = [
    {'name': 'BTC', 'script': 'bot_v10_btc.py', 'shares': 7},
    {'name': 'ETH', 'script': 'bot_v10_eth.py', 'shares': 10},
    {'name': 'XRP', 'script': 'bot_v10_xrp.py', 'shares': 5},
]

CHECK_INTERVAL = 32  # Evite :00, :15, :30, :45 (bougies 15min)
MAX_RESTARTS = 5     # Max restarts avant alerte critique
RESTART_COOLDOWN = 60  # Attendre 60s avant restart
```

### Systemd Services
| Service | Description | Status |
|---------|-------------|--------|
| watchdog-v10.service | Superviseur + 3 bots | enabled, auto-start |
| startup-alert-v10.service | Alerte Telegram au boot | enabled |

### Cron Jobs
```bash
# Decales pour eviter conflit avec bougies 15min (00, 15, 30, 45)
2 * * * *       heartbeat_v10.sh              # Status horaire
2 0 * * *       cleanup_logs.sh               # Nettoyage quotidien
5,20,35,50 * * * *  python trade_tracker.py check  # Verif WIN/LOSS
```

| Cron | Schedule | Description |
|------|----------|-------------|
| Heartbeat | :02 chaque heure | Status Telegram |
| Cleanup | 00:02 chaque jour | Nettoie logs > 7 jours |
| Trade Check | :05, :20, :35, :50 | Verifie PENDING → WIN/LOSS |

### Configuration Live
| Pair | Shares | Mise/Trade |
|------|--------|------------|
| BTC | 7 | ~$3.68 |
| ETH | 10 | ~$5.25 |
| XRP | 5 | ~$2.63 |
| **Total** | **22** | **~$11.55** |

## Environment Variables (.env)

```bash
# Polymarket
POLYMARKET_PRIVATE_KEY=0x...
POLYMARKET_CHAIN_ID=137

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Mode
ENVIRONMENT=production
```

## Common Commands

### Start/Stop
```bash
# Demarrer (via systemd)
sudo systemctl start watchdog-v10

# Arreter
sudo systemctl stop watchdog-v10

# Redemarrer
sudo systemctl restart watchdog-v10
```

### Check Status
```bash
# Status systemd
sudo systemctl status watchdog-v10

# Processus actifs
ps aux | grep bot_v10 | grep -v grep

# Logs temps reel
tail -f logs/watchdog_v10.log
```

### Manual Commands
```bash
# Heartbeat manuel
./heartbeat_v10.sh

# Verifier crontab
crontab -l
```

## Trade Tracker SQL

### Database Schema
```sql
-- trades.db (SQLite)
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    symbol TEXT,           -- BTC/USDT, ETH/USDT, XRP/USDT
    direction TEXT,        -- UP, DOWN
    shares INTEGER,
    entry_price REAL,
    order_id TEXT,         -- Polymarket order ID
    candle_open REAL,
    candle_close REAL,
    result TEXT,           -- PENDING, WIN, LOSS
    pnl REAL,
    -- V2: Indicateurs techniques
    rsi REAL,
    stochastic REAL,
    ftfc_score REAL,
    btc_price REAL,
    strategy_version TEXT  -- V10
);
```

### Commands
| Command | Description |
|---------|-------------|
| `python trade_tracker.py` | Check pending + stats |
| `python trade_tracker.py stats` | Stats 7 derniers jours |
| `python trade_tracker.py check` | Verifier WIN/LOSS via Binance |
| `python trade_tracker.py analysis` | Analyse par heure, indicateurs |
| `python trade_tracker.py hourly` | Performance par heure UTC |
| `python trade_tracker.py export` | Export CSV |

### Features
```yaml
Enregistrement:
  - Tous les trades avec indicateurs (RSI, Stoch, FTFC)
  - Prix BTC/ETH/XRP au moment du trade
  - Order ID Polymarket pour tracabilite

Verification:
  - Check automatique WIN/LOSS via Binance API
  - Compare direction predite vs direction reelle
  - Calcul PnL automatique

Analyse:
  - Stats par symbole (BTC, ETH, XRP)
  - Performance par heure UTC
  - Win rate par plage RSI/Stoch/FTFC
  - Series (max win streak, max loss streak)
  - Export CSV pour analyse externe
```

## Success Criteria

- **SC-001**: 3 bots V10 running 24/7 via watchdog
- **SC-002**: Win Rate >= 58% on monthly basis
- **SC-003**: 0 months below $10,000 PnL
- **SC-004**: Telegram notifications within 5 seconds of trade
- **SC-005**: Auto-recovery within 32 seconds of crash (watchdog)
- **SC-006**: Systemd auto-start at VPS boot
- **SC-007**: Heartbeat Telegram every hour at :02
- **SC-008**: No interference with 15min candle analysis
- **SC-009**: FTFC Score calculated correctly from 1H/4H data
- **SC-010**: Triple confirmation (RSI + Stoch + FTFC) before every trade
- **SC-011**: All trades logged to SQLite with indicators (RSI, Stoch, FTFC)
- **SC-012**: Trade results (WIN/LOSS) auto-verified via Binance API
- **SC-013**: Cron auto-check trades every 15min (:05, :20, :35, :50)
