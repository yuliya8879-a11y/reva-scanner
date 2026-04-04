#!/bin/bash
pkill -f "run_polling.py" 2>/dev/null
sleep 2
cd ~/reva-scanner
PYTHONUNBUFFERED=1 python3 -u run_polling.py > ~/reva-scanner/bot.log 2>&1 &
echo "✅ Бот перезапущен (PID: $!)"
