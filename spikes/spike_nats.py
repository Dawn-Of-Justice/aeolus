"""
spikes/spike_nats.py
Spike S5 — verify NATS pub/sub works on this machine.

Prerequisites:
  1. Install NATS server: https://nats.io/download/
     OR: winget install NATS.nats-server
     OR: docker run -p 4222:4222 nats
  2. pip install nats-py

Run: python spikes/spike_nats.py
Expected output: "✅ NATS spike PASSED"
"""
from __future__ import annotations

import asyncio
import time

import nats

NATS_URL = "nats://localhost:4222"
TOPIC = "aeolus.test"
MESSAGE = b'{"hello": "aeolus"}'
RECEIVED: list[bytes] = []


async def run():
    nc = await nats.connect(NATS_URL)
    print(f"✓ Connected to NATS at {NATS_URL}")

    async def handler(msg):
        RECEIVED.append(msg.data)
        print(f"  Received: {msg.data.decode()}")

    await nc.subscribe(TOPIC, cb=handler)
    print(f"✓ Subscribed to '{TOPIC}'")

    await asyncio.sleep(0.1)   # let subscription settle

    t0 = time.monotonic()
    await nc.publish(TOPIC, MESSAGE)
    await asyncio.sleep(0.2)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    await nc.drain()

    if RECEIVED and RECEIVED[0] == MESSAGE:
        print(f"\n✅ NATS spike PASSED — roundtrip ~{elapsed_ms}ms")
    else:
        print("\n❌ NATS spike FAILED — message not received")


if __name__ == "__main__":
    asyncio.run(run())
