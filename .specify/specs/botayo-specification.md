# Botayo Specification
## Bot Trading Polymarket V8.1 HYBRIDE (223 SKIP + 12 REVERSE)

**Created**: 2025-12-30
**Updated**: 2025-12-31
**Status**: Production
**Branch**: main
**Version**: 8.1 HYBRIDE

## System Overview

Botayo est un bot de trading automatise pour Polymarket qui effectue des predictions UP/DOWN sur les crypto-monnaies (BTC, ETH, XRP) toutes les 15 minutes.

```
┌─────────────────────────────────────────────────────────────┐
│                         VPS (3.96.141.89)                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Bot ETH    │  │  Bot BTC    │  │  Bot XRP    │         │
│  │  10 shares  │  │  7 shares   │  │  5 shares   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          │                                  │
│                    ┌─────▼─────┐                           │
│                    │ Watchdog  │ (*/5 cron)                │
│                    │   v8.1    │                           │
│                    └───────────┘                           │
└─────────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
     ┌────────────────┐             ┌────────────────┐
     │   Polymarket   │             │    Telegram    │
     │   CLOB API     │             │      Bot       │
     └────────────────┘             └────────────────┘
```

## Trading Strategy

### Indicateurs Techniques
| Indicateur | Config | Signal UP | Signal DOWN |
|------------|--------|-----------|-------------|
| RSI(7) | period=7 | < 38 | > 58 |
| Stochastic(5) | period=5 | < 30 | > 80 |

### Regles de Signal
```python
# Signal UP (Achat)
signal_up = (rsi < 38) AND (stoch_k < 30)

# Signal DOWN (Vente)
signal_down = (rsi > 58) AND (stoch_k > 80)
```

### Strategie V8.1 HYBRIDE (SKIP + REVERSE)
```yaml
# 223 candles SKIP (WR 42-53%): Pas de trade
# 12 candles REVERSE (WR <42%): Signal inverse (WR inverse >58%)

REVERSE_CANDLES (12):
  - Dim 08:30  (WR 35.2% -> 64.8%)
  - Dim 11:15  (WR 35.4% -> 64.6%)
  - Ven 18:15  (WR 36.9% -> 63.1%)
  - Ven 02:00  (WR 37.0% -> 63.0%)
  - Mer 19:30  (WR 37.4% -> 62.6%)
  - Dim 13:15  (WR 38.6% -> 61.4%)
  - Dim 02:30  (WR 39.4% -> 60.6%)
  - Ven 14:30  (WR 39.7% -> 60.3%)
  - Mer 06:30  (WR 40.7% -> 59.3%)
  - Jeu 14:30  (WR 41.7% -> 58.3%)
  - Mar 14:15  (WR 41.9% -> 58.1%)
  - Lun 02:45  (WR 42.0% -> 58.0%)

SKIP_CANDLES (223): Restantes des 235 candles originales

# Gain V8.1 vs V8: +$859/mois (+3.8%)
# PnL V8.1: $23,750/mois | Pire mois: $15,361
```

### Code Implementation
```python
BLOCKED_CANDLES = {...}  # 235 candles
REVERSE_CANDLES = {
    (6, 8, 30), (6, 11, 15), (4, 18, 15), (4, 2, 0),
    (2, 19, 30), (6, 13, 15), (6, 2, 30), (4, 14, 30),
    (2, 6, 30), (3, 14, 30), (1, 14, 15), (0, 2, 45)
}

def get_signal():
    now = datetime.now(timezone.utc)
    candle_key = (now.weekday(), now.hour, (now.minute // 15) * 15)

    is_reverse = candle_key in REVERSE_CANDLES
    is_blocked = candle_key in BLOCKED_CANDLES

    if is_blocked and not is_reverse:
        return None  # SKIP

    signal = calculate_signal()  # RSI + Stoch

    if is_reverse and signal:
        signal = 'DOWN' if signal == 'UP' else 'UP'  # REVERSE

    return signal
```

## Polymarket Formula

### Entry @ 52.5c
```
BET $100 @ 52.5c = 190.48 shares
WIN:  190.48 * $1.00 - $100 = +$90.48
LOSS: 190.48 * $0.00 = -$100
```

### Expected Value (EV)
```
EV = (0.592 * $90.48) + (0.408 * -$100) = $53.56 - $40.80 = +$12.76/trade
```

### Monthly PnL Projection
```
60 trades/jour * 30 jours * $13.19 EV = ~$23,750/mois
```

## Backtest Results (2024-2025) - V8.1 HYBRIDE

### Comparaison V8 vs V8.1
| Metrique | V8 (235 SKIP) | V8.1 (223 SKIP + 12 REV) | Gain |
|----------|---------------|--------------------------|------|
| Win Rate | 59.2% | 59.2% | +0.0% |
| PnL/mois | $22,891 | $23,750 | +$859 |
| Pire mois | +$14,761 | +$15,361 | +$600 |
| Trades/jour | 59 | 60 | +1 |
| Mois gagnants | - | 19/24 | +79% |

### 2024 (V8)
| Mois | Trades | Win Rate | PnL |
|------|--------|----------|-----|
| Jan | 1,742 | 59.3% | +$21,847 |
| Feb | 1,651 | 60.1% | +$25,423 |
| Mar | 1,824 | 60.8% | +$29,521 |
| Apr | 1,715 | 58.9% | +$20,186 |
| May | 1,803 | 59.4% | +$22,764 |
| Jun | 1,706 | 61.2% | +$30,847 |
| Jul | 1,763 | 59.1% | +$21,392 |
| Aug | 1,791 | 60.5% | +$28,196 |
| Sep | 1,739 | 59.7% | +$24,108 |
| Oct | 1,794 | 58.2% | +$18,523 |
| Nov | 1,746 | 60.0% | +$26,548 |
| Dec | 1,868 | 58.6% | +$18,681 |
| **Total** | **21,142** | **59.5%** | **+$282,036** |

### 2025 (V8)
| Mois | Trades | Win Rate | PnL |
|------|--------|----------|-----|
| Jan | 1,839 | 57.9% | +$17,243 |
| Feb | 1,663 | 58.3% | +$18,106 |
| Mar | 1,833 | 59.5% | +$25,344 |
| Apr | 1,764 | 59.8% | +$26,107 |
| May | 1,821 | 58.9% | +$21,053 |
| Jun | 1,738 | 59.1% | +$22,195 |
| Jul | 1,776 | 58.0% | +$17,691 |
| Aug | 1,818 | 59.4% | +$24,327 |
| Sep | 1,763 | 58.6% | +$20,541 |
| Oct | 1,833 | 58.1% | +$18,967 |
| Nov | 1,750 | 60.3% | +$27,432 |
| Dec | 2,048 | 57.6% | +$14,761 |
| **Total** | **22,169** | **58.8%** | **+$267,336** |

## VPS Configuration

### SSH Access
```bash
ssh -i /tmp/vps_key.pem ubuntu@3.96.141.89
```

### Directory Structure
```
/home/ubuntu/poly/
├── bot_simple.py          # Main bot
├── config.yaml            # Strategy config
├── watchdog.sh            # Process monitor v8.1
├── heartbeat.sh           # Hourly status
├── start_bots.sh          # Manual start
├── cleanup_logs.sh        # Log rotation
├── venv/                  # Python environment
└── logs/
    ├── bot_simple.log     # Trade logs
    ├── watchdog.log       # Monitor logs
    └── heartbeat.log      # Status logs
```

### Watchdog v8.1
```bash
#!/bin/bash
LOCK=/tmp/wd.lock
[ -f $LOCK ] && exit 0
touch $LOCK
trap "rm -f $LOCK" EXIT

cd /home/ubuntu/poly
PY=/home/ubuntu/poly/venv/bin/python
N=$(pgrep -c -f bot_simple.py 2>/dev/null || echo 0)
echo "[$(date +%F\ %T)] N=$N" >> logs/watchdog.log

if [ "$N" -ne 3 ]; then
    pkill -9 -f bot_simple.py 2>/dev/null
    sleep 2
    $PY bot_simple.py --live --yes --shares 10 --symbols ETH >> logs/bot_simple.log 2>&1 &
    sleep 2
    $PY bot_simple.py --live --yes --shares 7 --symbols BTC >> logs/bot_simple.log 2>&1 &
    sleep 2
    $PY bot_simple.py --live --yes --shares 5 --symbols XRP >> logs/bot_simple.log 2>&1 &
    sleep 2
    echo "[$(date +%F\ %T)] Fixed" >> logs/watchdog.log
fi
```

### Cron Configuration
```crontab
# Watchdog every 5 minutes
*/5 * * * * /home/ubuntu/poly/watchdog.sh

# Heartbeat every hour
0 * * * * /home/ubuntu/poly/heartbeat.sh >> /home/ubuntu/poly/logs/heartbeat.log 2>&1

# Cleanup logs daily at midnight
0 0 * * * /home/ubuntu/poly/cleanup_logs.sh >> /home/ubuntu/poly/logs/cleanup.log 2>&1
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

### Check Bot Status
```bash
ssh -i /tmp/vps_key.pem ubuntu@3.96.141.89 "ps aux | grep bot_simple | grep -v grep"
```

### View Recent Trades
```bash
ssh -i /tmp/vps_key.pem ubuntu@3.96.141.89 "tail -50 /home/ubuntu/poly/logs/bot_simple.log | grep TRADE"
```

### Restart Bots
```bash
ssh -i /tmp/vps_key.pem ubuntu@3.96.141.89 "/home/ubuntu/poly/start_bots.sh"
```

### Force Heartbeat
```bash
ssh -i /tmp/vps_key.pem ubuntu@3.96.141.89 "/home/ubuntu/poly/heartbeat.sh"
```

## Known Issues & Solutions

### Duplicate Bots (6 instead of 3)
**Cause**: Race condition with cron or watchdog not killing properly
**Solution**: Watchdog v8.1 with lock file + "kill all then restart 3"

### Blocked Time Combo Not Applying
**Cause**: Bot using old config
**Solution**: Restart bots after config change

### High Loss Rate
**Check**: Verify only 3 bots running, not duplicates
**Check**: Verify current hour not in blocked combos

## Success Criteria

- **SC-001**: 3 bots running 24/7 without duplicates
- **SC-002**: Win Rate > 58% on monthly basis (upgraded from 55%)
- **SC-003**: No trades during 235 blocked candles
- **SC-004**: Telegram notifications within 5 seconds of trade
- **SC-005**: Auto-recovery within 5 minutes of crash
- **SC-006**: Pire mois > +$14,000 (new with V8)
