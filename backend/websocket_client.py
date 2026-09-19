import asyncio
import json
import websockets
import sys

job_id = sys.argv[1]
token = sys.argv[2]

async def main():
    uri=f"ws://localhost:8000/api/diagnosis/ws/{job_id}?token={token}"

    print("Connecting to:")
    print(f"ws://localhost:8000/api/diagnosis/ws/{job_id}?token=***")
    print()

    try:
        async with websockets.connect(uri, proxy=None) as websocket:
            print("WEBSOCKET CONNECTED")
            print("-" * 60)

            while True:
                message = await websocket.recv()
                data = json.loads(message)

                print(json.dumps(data, indent=2))
                print("-" * 60)

                if data.get("event") in {
                    "diagnosis_completed",
                    "diagnosis_failed",
                }:
                    break

    except Exception as error:
        print("WEBSOCKET ERROR:", repr(error))
        raise

asyncio.run(main())
