"""Event Hooks"""

from argparse import Namespace

from deltabot_cli import (
    AttrDict,
    Bot,
    BotCli,
    ChatType,
    EventType,
    events,
    is_not_known_command,
)

from .api import dc2mb, init_api
from .util import get_log_level

cli = BotCli("matterdelta", log_level=get_log_level())


@cli.on_init
def _on_init(bot: Bot, _args: Namespace) -> None:
    for accid in bot.rpc.get_all_account_ids():
        if not bot.rpc.get_config(accid, "displayname"):
            bot.rpc.set_config(accid, "displayname", "Matterbridge Bot")
            status = "I am a Delta Chat bot, send me /help for more info"
            bot.rpc.set_config(accid, "selfstatus", status)
            bot.rpc.set_config(accid, "delete_server_after", "1")


@cli.on_start
def _on_start(bot: Bot, args: Namespace) -> None:
    init_api(bot, args.config_dir)


@cli.on(events.RawEvent)
def _log_event(bot: Bot, accid: int, event: AttrDict) -> None:
    if event.kind == EventType.INFO:
        bot.logger.info(event.msg)
    elif event.kind == EventType.WARNING:
        bot.logger.warning(event.msg)
    elif event.kind == EventType.ERROR:
        bot.logger.error(event.msg)
    elif event.kind == EventType.SECUREJOIN_INVITER_PROGRESS:
        if event.progress == 1000:
            bot.logger.debug("QR scanned by contact id=%s", event.contact_id)
            chatid = bot.rpc.create_chat_by_contact_id(accid, event.contact_id)
            _send_help(bot, accid, chatid)


@cli.on(events.NewMessage(is_info=False, is_bot=None, func=is_not_known_command))
def _bridge(bot: Bot, accid: int, event: AttrDict) -> None:
    msg = event.msg
    chat = bot.rpc.get_basic_chat_info(accid, msg.chat_id)
    if chat.chat_type == ChatType.SINGLE and not msg.is_bot:
        bot.rpc.markseen_msgs(accid, [msg.id])
        _send_help(bot, accid, msg.chat_id)
    else:
        dc2mb(bot, accid, msg)


@cli.on(events.NewMessage(command="/id"))
def _id(bot: Bot, accid: int, event: AttrDict) -> None:
    msg = event.msg
    bot.rpc.markseen_msgs(accid, [msg.id])
    chat = bot.rpc.get_basic_chat_info(accid, msg.chat_id)
    if chat.chat_type == ChatType.SINGLE:
        text = "You can't use /id command here, add me to a group and use the command there"
        bot.rpc.send_msg(accid, msg.chat_id, {"text": text, "quotedMessageId": msg.id})
    else:
        reply = {"text": f"accountId: {accid}\nchatId: {msg.chat_id}"}
        bot.rpc.send_msg(accid, msg.chat_id, reply)


def _send_help(bot: Bot, accid: int, chatid: int) -> None:
    text = (
        "**Available commands**\n\n"
        "/id - send me this command in a group to get its ID."
    )
    bot.rpc.send_msg(accid, chatid, {"text": text})
