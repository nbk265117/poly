# Botayo Specification
## Bot Trading Polymarket v7.0 (44 Filtres Temporels)

**Created**: 2025-12-30
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

### 44 Combos Bloques (WR < 53%)
```yaml
Lundi:    0h, 1h, 2h, 3h, 6h, 7h, 14h, 15h, 18h, 20h
Mardi:    1h, 4h, 5h, 7h, 14h, 16h, 18h, 19h, 22h
Mercredi: 0h, 3h, 8h, 17h, 19h, 23h
Jeudi:    4h, 5h, 9h, 16h, 22h
Vendredi: 2h, 5h, 6h, 7h, 10h, 14h, 15h, 17h, 18h
Samedi:   3h
Dimanche: 8h, 13h, 22h, 23h
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
EV = (0.57 * $90.48) + (0.43 * -$100) = $51.57 - $43 = +$8.57/trade
```

### Monthly PnL Projection
```
66 trades/jour * 30 jours * $8.57 EV = ~$17,000/mois
```

## Backtest Results (2024-2025)

### 2024
| Mois | Trades | Win Rate | PnL |
|------|--------|----------|-----|
| Jan | 1,991 | 57.2% | +$16,298 |
| Feb | 1,884 | 58.4% | +$19,831 |
| Mar | 2,087 | 56.5% | +$14,508 |
| Apr | 1,961 | 56.3% | +$13,737 |
| May | 2,063 | 57.1% | +$17,237 |
| Jun | 1,951 | 58.8% | +$22,251 |
| Jul | 2,016 | 57.2% | +$17,404 |
| Aug | 2,048 | 56.7% | +$15,744 |
| Sep | 1,989 | 58.1% | +$20,604 |
| Oct | 2,052 | 55.7% | +$10,951 |
| Nov | 1,995 | 58.9% | +$23,067 |
| Dec | 2,095 | 57.3% | +$19,597 |
| **Total** | **24,132** | **57.3%** | **+$222,229** |

### 2025 (Jan-Dec projection)
| Mois | Trades | Win Rate | PnL |
|------|--------|----------|-----|
| Jan | 2,105 | 55.9% | +$11,807 |
| Feb | 1,903 | 56.0% | +$11,043 |
| Mar | 2,098 | 58.1% | +$21,595 |
| Apr | 2,018 | 55.9% | +$11,307 |
| May | 2,084 | 56.9% | +$16,218 |
| Jun | 1,989 | 56.9% | +$15,549 |
| Jul | 2,032 | 55.7% | +$10,699 |
| Aug | 2,081 | 57.7% | +$19,361 |
| Sep | 2,017 | 56.9% | +$15,929 |
| Oct | 2,098 | 56.3% | +$14,008 |
| Nov | 2,003 | 57.5% | +$17,857 |
| Dec | 2,343 | 56.1% | +$13,479 |
| **Total** | **24,771** | **56.6%** | **+$191,852** |

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
- **SC-002**: Win Rate > 55% on monthly basis
- **SC-003**: No trades during blocked time combos
- **SC-004**: Telegram notifications within 5 seconds of trade
- **SC-005**: Auto-recovery within 5 minutes of crash
