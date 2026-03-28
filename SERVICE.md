# Fantasy Baseball Bot - systemd Service

## Install

```bash
sudo cp /home/dev/proj/MLBFantasyAlertBot/fantasy-baseball-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fantasy-baseball-bot
sudo systemctl start fantasy-baseball-bot
```

## Manage

```bash
sudo systemctl status fantasy-baseball-bot    # check status
sudo systemctl start fantasy-baseball-bot     # start
sudo systemctl stop fantasy-baseball-bot      # stop
sudo systemctl restart fantasy-baseball-bot   # restart
```

## Logs

```bash
journalctl -u fantasy-baseball-bot -f         # watch live
journalctl -u fantasy-baseball-bot --since today  # today's logs
journalctl -u fantasy-baseball-bot -n 50      # last 50 lines
```

## Notes

- Auto-starts on boot
- Auto-restarts on crash (30s delay)
- Edit env vars in `run.sh`, then `sudo systemctl restart fantasy-baseball-bot`
