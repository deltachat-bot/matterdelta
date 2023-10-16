"""Matterbridge API interaction"""
import base64
import json
import logging
import os
import tempfile
import time
from threading import Thread

import requests
from deltabot_cli import AttrDict, Bot, const

mb_config = {}
id2gateway = {}
gateway2id = {}


def init_api(bot: Bot, config_dir: str) -> None:
    """Load matterbridge API configuration and start listening to the API endpoint."""
    path = os.path.join(config_dir, "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as config:
            mb_config.update(json.load(config))

    for gateway in mb_config.get("gateways") or []:
        gateway2id[gateway["gateway"]] = gateway["chatId"]
        id2gateway[gateway["chatId"]] = gateway["gateway"]

    if len(mb_config.get("gateways") or []):
        Thread(target=listen_to_matterbridge, args=(bot,)).start()


def dc2mb(msg: AttrDict) -> None:
    """Send a Delta Chat message to the matterbridge side."""
    gateway = id2gateway.get(msg.chat_id)
    if gateway:
        api_url = mb_config["api"]["url"]
        token = mb_config["api"].get("token", "")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        sender = msg.sender.get_snapshot()
        username = msg.override_sender_name or sender.display_name
        if not msg.text and not msg.file:
            return
        text = msg.text
        if text and text.split(maxsplit=1)[0] == "/me":
            event = "user_action"
            text = text[3:].strip()
        else:
            event = ""
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
        data = {"gateway": gateway, "username": username, "text": text, "event": event}
        if msg.file:
            with open(msg.file, mode="rb") as attachment:
                enc_data = base64.standard_b64encode(attachment.read()).decode()
            data["Extra"] = {
                "file": [{"Name": msg.file_name, "Data": enc_data, "Comment": text}]
            }
        logging.debug("DC->MB %s", data)
        requests.post(api_url + "/api/message", json=data, headers=headers, timeout=60)


def mb2dc(bot: Bot, msg: dict) -> None:
    """Send a message from matterbridge to the bridged Delta Chat group"""
    if msg["event"] not in ("", "user_action"):
        return
    chat_id = gateway2id.get(msg["gateway"])
    if not chat_id:
        return
    chat = bot.account.get_chat_by_id(chat_id)
    text = msg.get("text") or ""
    if msg["event"] == "user_action":
        text = "/me " + text
    file = ((msg.get("Extra") or {}).get("file") or [{}])[0]
    if file:
        if text == file["Name"]:
            text = ""
        with tempfile.TemporaryDirectory() as tmp_dir:
            filename = os.path.join(tmp_dir, file["Name"])
            data = base64.decodebytes(file["Data"].encode())
            with open(filename, mode="wb") as attachment:
                attachment.write(data)
            is_sticker = file["Name"].endswith((".tgs", ".webp"))
            viewtype = const.ViewType.STICKER if is_sticker else None
            chat.send_message(
                text=text,
                file=filename,
                viewtype=viewtype,
                override_sender_name=msg["username"],
            )
    elif text:
        chat.send_message(text=text, override_sender_name=msg["username"])


def listen_to_matterbridge(bot: Bot) -> None:
    """Process forever the streams of messages from matterbridge API"""
    logging.debug("Listening to matterbridge API...")
    api_url = mb_config["api"]["url"]
    token = mb_config["api"].get("token", "")
    headers = {"Authorization": f"Bearer {token}"} if token else None
    with requests.Session() as session:
        while True:
            try:
                # use the /api/messages endpoint because /api/stream have issues:
                # https://github.com/42wim/matterbridge/issues/1983
                with session.get(api_url + "/api/messages", headers=headers) as resp:
                    for msg in resp.json():
                        logging.debug(msg)
                        mb2dc(bot, msg)
                time.sleep(1)
            except Exception as ex:  # pylint: disable=W0703
                time.sleep(5)
                logging.exception(ex)
