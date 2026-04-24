# hive-client

Python client SDK for the [Hive](https://app.hive-memory.com) memory API.

## Installation

```bash
pip install hive-client
```

## Quick start

```python
import asyncio
from hive_client import HiveClient

client = HiveClient(api_key="hive_sk_...")

# Async
async def main():
    await client.remember("my-key", "my value", tags=["tag1"])
    memory = await client.recall("my-key")
    print(memory.value)

asyncio.run(main())

# Sync convenience wrappers
client.sync_remember("my-key", "my value")
memory = client.sync_recall("my-key")
```
