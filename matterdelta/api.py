"""Matterbridge API interaction"""
import asyncio
import base64
import json
import logging
import os

import aiofiles
import aiohttp
from deltabot_cli import AttrDict, Bot, const

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
        gateway2id[gateway["gateway"]] = gateway["chatId"]
        id2gateway[gateway["chatId"]] = gateway["gateway"]

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
        url = await upload_media(msg.file) if msg.file else ""
        if url and msg.text:
            text = f"{url} - {msg.text}"
        else:
            text = url or msg.text
        if not text:
            return
        if msg.quote and mb_config.get("quoteFormat"):
            quotenick = (
                msg.quote.get("override_sender_name")
                or msg.quote.get("author_display_name")
                or ""
            )
            text = mb_config["quoteFormat"].format(
                MESSAGE=text,
                QUOTENICK=quotenick,
                QUOTEMESSAGE=" ".join(msg.quote.text.split()),
            )
        data = {"gateway": gateway, "username": username, "text": text}
        logging.debug("DC->MB %s", data)
        async with aiohttp.ClientSession(api_url, headers=headers) as session:
            async with session.post("/api/message", json=data):
                pass


async def mb2dc(bot: Bot, msg: dict) -> None:
    """Send a message from matterbridge to the bridged Delta Chat group"""
    if msg["event"]:
        return
    chat_id = gateway2id.get(msg["gateway"])
    if not chat_id:
        return
    chat = bot.account.get_chat_by_id(chat_id)
    text = msg.get("text")
    file = ((msg.get("Extra") or {}).get("file") or [{}])[0]
    if file:
        if text == file["Name"]:
            text = ""
        async with aiofiles.tempfile.TemporaryDirectory() as tmp_dir:
            filename = os.path.join(tmp_dir, file["Name"])
            data = base64.decodebytes(file["Data"].encode())
            async with aiofiles.open(filename, mode="wb") as attachment:
                await attachment.write(data)
            is_sticker = file["Name"].endswith((".tgs", ".webp"))
            viewtype = const.ViewType.STICKER if is_sticker else None
            await chat.send_message(
                text=text,
                file=filename,
                viewtype=viewtype,
                override_sender_name=msg["username"],
            )
    elif text:
        await chat.send_message(text=text, override_sender_name=msg["username"])


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


async def upload_media(path: str) -> str:
    """Try to upload attachment"""
    cmd = mb_config.get("mediaUploadCmd")
    if not cmd:
        return ""

    process = await asyncio.create_subprocess_shell(
        cmd.format(FILE=path), stdout=asyncio.subprocess.PIPE
    )
    if await process.wait() == 0 and process.stdout is not None:
        url = await process.stdout.read()
        try:
            return url.decode().strip()
        except UnicodeDecodeError:
            pass
    return ""
