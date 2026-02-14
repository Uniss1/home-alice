# agent/main.py
import asyncio
import json
import logging
import os
import websockets
from agent.config import load_config
from agent.llm_client import LLMClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_agent(config_path: str):
    config = load_config(config_path)
    llm = LLMClient(
        config=config.llm,
        vk_token=config.vk_token,
        browser_cdp_url=config.browser_cdp_url,
        allowed_commands=config.allowed_commands,
    )
    url = f"{config.server_url}?key={config.api_key}"

    while True:
        try:
            logger.info("Connecting to %s", config.server_url)
            async with websockets.connect(url) as ws:
                logger.info("Connected to relay server")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        msg_id = data.get("id", "")
                        text = data.get("text", "")
                        logger.info("Received command: %s", text)

                        # Process via LLM (runs in thread to not block)
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None, llm.process_command, text
                        )
                        logger.info("Result: %s", result)

                        # Send response back
                        response = json.dumps({"id": msg_id, "text": result})
                        await ws.send(response)

                    except Exception as e:
                        logger.error("Error processing message: %s", e)
                        try:
                            error_resp = json.dumps({
                                "id": data.get("id", ""),
                                "text": f"Ошибка: {e}",
                            })
                            await ws.send(error_resp)
                        except Exception:
                            pass

        except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
            logger.warning("Connection lost: %s. Reconnecting in 5s...", e)
            await asyncio.sleep(5)
        except Exception as e:
            logger.error("Unexpected error: %s. Reconnecting in 5s...", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    config_file = os.environ.get("CONFIG_PATH", "agent/config.yaml")
    asyncio.run(run_agent(config_file))
