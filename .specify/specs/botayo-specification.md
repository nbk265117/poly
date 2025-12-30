# Botayo Specification
## Bot Trading Polymarket v8.0 (235 Filtres 15min)

**Created**: 2025-12-30
**Updated**: 2025-12-31
**Status**: Production
**Branch**: main

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

### 235 Candles Bloquees (WR < 53%)
```yaml
# Filtrage au niveau des candles 15min (plus precis que les heures)
# Format: (jour, heure, minute) - minute = 0, 15, 30, ou 45

Lundi:    37 candles (00:00-03:45, 06:00-07:45, 14:00-15:45, 18:00-18:45, 20:00-20:45)
Mardi:    34 candles (01:00-01:45, 04:00-05:45, 07:00-07:45, 14:00-14:45, 16:00-16:45, 18:00-19:45, 22:00-22:45)
Mercredi: 28 candles (00:00-00:45, 03:00-03:45, 08:00-08:45, 17:00-17:45, 19:00-19:45, 23:00-23:45)
Jeudi:    22 candles (04:00-05:45, 09:00-09:45, 16:00-16:45, 22:00-22:45)
Vendredi: 35 candles (02:00-02:45, 05:00-07:45, 10:00-10:45, 14:00-15:45, 17:00-18:45)
Samedi:   6 candles  (03:00-03:45, 15:00-15:45)
Dimanche: 18 candles (08:00-08:45, 13:00-13:45, 22:00-23:45)

# Total: 235 candles bloquees = ~35% du temps
# Gain vs V7 (44 heures): +$5,655/mois (+33%)
```

### Code Implementation
```python
BLOCKED_CANDLES = {
    (0, 0, 0), (0, 0, 15), (0, 0, 30), (0, 0, 45),  # Lun 00h
    # ... 235 tuples (day, hour, minute)
}

def get_signal():
    now = datetime.now(timezone.utc)
    candle_key = (now.weekday(), now.hour, (now.minute // 15) * 15)
    if candle_key in BLOCKED_CANDLES:
        return None  # Skip this candle
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
59 trades/jour * 30 jours * $12.76 EV = ~$22,600/mois
```

## Backtest Results (2024-2025) - V8 avec 235 Filtres 15min

### Comparaison V7 vs V8
| Metrique | V7 (44 heures) | V8 (235 candles) | Gain |
|----------|----------------|------------------|------|
| Win Rate | 57.0% | 59.2% | +2.2% |
| PnL/mois | $17,236 | $22,891 | +$5,655 |
| Pire mois | +$9,109 | +$14,761 | +$5,652 |
| Trades/jour | 66 | 59 | -7 |

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
