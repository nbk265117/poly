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

### Directory Structure
```
/home/ubuntu/poly/
├── bot_v10_btc.py         # Bot BTC V10
├── bot_v10_eth.py         # Bot ETH V10
├── bot_v10_xrp.py         # Bot XRP V10
├── watchdog_v10.py        # Process monitor V10
├── config.yaml            # Strategy config
├── venv/                  # Python environment
└── logs/
    ├── bot_v10_btc.log    # BTC trade logs
    ├── bot_v10_eth.log    # ETH trade logs
    ├── bot_v10_xrp.log    # XRP trade logs
    └── watchdog_v10.log   # Monitor logs
```

### Watchdog V10
```python
BOTS = [
    {'name': 'BTC', 'script': 'bot_v10_btc.py', 'process': None},
    {'name': 'ETH', 'script': 'bot_v10_eth.py', 'process': None},
    {'name': 'XRP', 'script': 'bot_v10_xrp.py', 'process': None},
]

CHECK_INTERVAL = 30  # Verification toutes les 30 secondes
MAX_RESTARTS = 5     # Max restarts avant alerte critique
RESTART_COOLDOWN = 60  # Attendre 60s avant restart
```

## Environment Variables (.env)

```bash
# Polymarket
POLYMARKET_PRIVATE_KEY=0x...

# Telegram
TELEGRAM_TOKEN=...
TELEGRAM_CHAT_ID=...

# Mode
ENVIRONMENT=production  # or development
```

## Common Commands

### Start Bots
```bash
# Paper Trading
python watchdog_v10.py

# Live Trading
python watchdog_v10.py --live --yes
```

### Check Bot Status
```bash
ps aux | grep bot_v10 | grep -v grep
```

### View Recent Trades
```bash
tail -50 logs/bot_v10_btc.log | grep TRADE
```

## Success Criteria

- **SC-001**: 3 bots V10 running 24/7 without duplicates
- **SC-002**: Win Rate >= 58% on monthly basis
- **SC-003**: 0 months below $10,000 PnL
- **SC-004**: Telegram notifications within 5 seconds of trade
- **SC-005**: Auto-recovery within 30 seconds of crash
- **SC-006**: FTFC Score calculated correctly from 1H/4H data
- **SC-007**: Triple confirmation (RSI + Stoch + FTFC) before every trade
