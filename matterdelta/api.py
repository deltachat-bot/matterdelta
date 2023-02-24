"""Matterbridge API interaction"""
import asyncio
import json
import logging
import os

import httpx
from deltabot_cli import AttrDict, Bot

from .util import run_in_background

mb_config = {}
id2gateway = {}
gateway2id = {}


async def init_api(bot: Bot, config_dir: str) -> None:
    """Load matterbridge API configuration and start listening to the API endpoint."""
    path = os.path.join(config_dir, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as config:
            mb_config.update(json.load(config))

    for gateway in mb_config.get("gateways") or []:
        gateway2id[gateway["gateway"]] = gateway["chat-id"]
        id2gateway[gateway["chat-id"]] = gateway["gateway"]

    if len(mb_config.get("gateways") or []):
        run_in_background(listen_to_matterbridge(bot))


async def dc2mb(msg: AttrDict) -> None:
    """Send a Delta Chat message to the matterbridge side."""
    gateway = id2gateway.get(msg.chat_id)
    if gateway:
        api_url = mb_config["api"]["url"]
        token = mb_config["api"].get("token", "")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        sender = await msg.sender.get_snapshot()
        username = msg.override_sender_name or sender.display_name
        data = {"gateway": gateway, "username": username, "text": msg.text}
        async with httpx.AsyncClient() as client:
            await client.post(f"{api_url}/api/message", data=data, headers=headers)


async def mb2dc(bot: Bot, msg: dict) -> None:
    """Send a message from matterbridge to the bridged Delta Chat group"""
    if msg["event"]:
        return
    chat_id = gateway2id.get(msg["gateway"])
    if not chat_id or not msg.get("text"):
        return
    chat = bot.account.get_chat_by_id(chat_id)
    await chat.send_message(text=f"{msg['username']}: {msg['text']}")


async def listen_to_matterbridge(bot: Bot) -> None:
    """Process forever the streams of messages from matterbridge API"""
    logging.debug("Listening to matterbridge API...")
    api_url = mb_config["api"]["url"]
    url = f"{api_url}/api/stream"
    token = mb_config["api"].get("token", "")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    timeout = httpx.Timeout(10, read=None)
    while True:
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    method="GET", url=url, timeout=timeout, headers=headers
                ) as res:
                    async for line in res.aiter_lines():
                        logging.debug(line)
                        await mb2dc(bot, json.loads(line))
        except Exception as ex:  # pylint: disable=W0703
            await asyncio.sleep(5)
            logging.exception(ex)
