# media_assistant/main.py
import asyncio
from media_assistant.config import load_config


async def main():
    config = load_config("media_assistant/config.yaml")
    # TODO: Initialize components
    print("Media Assistant starting...")


if __name__ == "__main__":
    asyncio.run(main())
