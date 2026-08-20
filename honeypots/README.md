# TrapNet DataTrap Honeypot Integration

Adapts [DataTrap](https://github.com/ThalesGroup/dd-honeypot) honeypot logs into the
standard TrapNet event schema and publishes them to Redis stream
`honeypot_events`.

## Directory Structure

```
honeypots/
├── datatrap-config/
│   ├── fake-ssh/
│   │   ├── config.json      # SSH honeypot config (port 2222)
│   │   └── data.jsonl       # Sample SSH interactions dataset
│   └── fake-http/
│       ├── config.json      # HTTP honeypot config (port 8080)
│       └── data.jsonl       # Sample HTTP interactions dataset
├── event_adapter.py         # Log tailer + classifier + Redis publisher
├── requirements.txt
├── Dockerfile
└── README.md
```

## Running

### Standalone

```bash
pip install -r requirements.txt
export REDIS_HOST=localhost
export HONEYPOT_LOG_DIR=/var/log/honeypot
python event_adapter.py
```

### Docker

```bash
docker build -t trapnet-event-adapter .
docker run --network host \
  -v /var/log/honeypot:/var/log/honeypot \
  -e REDIS_HOST=localhost \
  trapnet-event-adapter
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_STREAM` | `honeypot_events` | Target Redis stream name |
| `HONEYPOT_LOG_DIR` | `/var/log/honeypot` | Directory to watch for `.json` logs |
| `POLL_INTERVAL` | `1.0` | Seconds between file-poll cycles |
| `MAX_STREAM_LEN` | `50000` | Max Redis stream length (trimmed) |

## Technique Classification

| Technique | Trigger |
|---|---|
| `buffer_overflow_probe` | Payload > 100 characters |
| `command_injection` | Shell metacharacters: `; \| & \` $ ( ) { }` |
| `sql_injection` | SQL keywords: SELECT, UNION, DROP, etc. |
| `credential_bruteforce` | Failed SSH login attempt |
| `unknown` | No matching pattern |
