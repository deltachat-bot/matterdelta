"""Matterbridge API interaction"""
import asyncio
import json
import logging
import os

import aiohttp
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
        logging.debug("DC->MB %s", data)
        async with aiohttp.ClientSession(api_url, headers=headers) as session:
            async with session.post("/api/message", json=data):
                pass


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
    token = mb_config["api"].get("token", "")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    while True:
        try:
            async with aiohttp.ClientSession(api_url, headers=headers) as session:
                # use the /api/messages endpoint because /api/stream have issues:
                # https://github.com/42wim/matterbridge/issues/1983
                async with session.get("/api/messages") as resp:
                    for msg in await resp.json():
                        logging.debug(msg)
                        await mb2dc(bot, msg)
            await asyncio.sleep(1)
        except Exception as ex:  # pylint: disable=W0703
            await asyncio.sleep(5)
            logging.exception(ex)
