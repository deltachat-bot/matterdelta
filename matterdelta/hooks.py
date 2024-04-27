"""Event Hooks"""

from argparse import Namespace

from deltabot_cli import BotCli
from deltachat2 import Bot, ChatType, CoreEvent, EventType, MsgData, NewMsgEvent, events
from rich.logging import RichHandler

from ._version import __version__
from .api import dc2mb, init_api

cli = BotCli("matterdelta")
cli.add_generic_option("-v", "--version", action="version", version=__version__)
cli.add_generic_option(
    "--no-time",
    help="do not display date timestamp in log messages",
    action="store_false",
)


@cli.on_init
def _on_init(bot: Bot, args: Namespace) -> None:
    bot.logger.handlers = [
        RichHandler(show_path=False, omit_repeated_times=False, show_time=args.no_time)
    ]
    for accid in bot.rpc.get_all_account_ids():
        if not bot.rpc.get_config(accid, "displayname"):
            bot.rpc.set_config(accid, "displayname", "Matterbridge Bot")
            status = "I am a Delta Chat bot, send me /help for more info"
            bot.rpc.set_config(accid, "selfstatus", status)
            bot.rpc.set_config(accid, "delete_device_after", str(60 * 60 * 24 * 30))


@cli.on_start
def _on_start(bot: Bot, args: Namespace) -> None:
    init_api(bot, args.config_dir)


@cli.on(events.RawEvent)
def _log_event(bot: Bot, accid: int, event: CoreEvent) -> None:
    if event.kind == EventType.INFO:
        bot.logger.debug(event.msg)
    elif event.kind == EventType.WARNING:
        bot.logger.warning(event.msg)
    elif event.kind == EventType.ERROR:
        bot.logger.error(event.msg)
    elif event.kind == EventType.SECUREJOIN_INVITER_PROGRESS:
        if event.progress == 1000:
            if not bot.rpc.get_contact(accid, event.contact_id).is_bot:
                bot.logger.debug("QR scanned by contact id=%s", event.contact_id)
                chatid = bot.rpc.create_chat_by_contact_id(accid, event.contact_id)
                _send_help(bot, accid, chatid)


@cli.on(events.NewMessage(is_info=False, is_bot=None))
def _bridge(bot: Bot, accid: int, event: NewMsgEvent) -> None:
    if bot.has_command(event.command):
        return
    msg = event.msg
    chat = bot.rpc.get_basic_chat_info(accid, msg.chat_id)
    if chat.chat_type == ChatType.SINGLE and not msg.is_bot:
        bot.rpc.markseen_msgs(accid, [msg.id])
        _send_help(bot, accid, msg.chat_id)
    else:
        dc2mb(bot, accid, msg)


@cli.on(events.NewMessage(command="/id"))
def _id(bot: Bot, accid: int, event: NewMsgEvent) -> None:
    msg = event.msg
    bot.rpc.markseen_msgs(accid, [msg.id])
    chat = bot.rpc.get_basic_chat_info(accid, msg.chat_id)
    if chat.chat_type == ChatType.SINGLE:
        text = "You can't use /id command here, add me to a group and use the command there"
        reply = MsgData(text=text, quoted_message_id=msg.id)
    else:
        reply = MsgData(text=f"accountId: {accid}\nchatId: {msg.chat_id}")
    bot.rpc.send_msg(accid, msg.chat_id, reply)


def _send_help(bot: Bot, accid: int, chatid: int) -> None:
    text = (
        "I'm a bot, I allow to bridge Delta Chat groups with groups in other platforms."
        " Only the bot administrator can bridge groups.\n\n"
        "**Available commands**\n\n"
        "/id - send me this command in a group to get its ID."
    )
    bot.rpc.send_msg(accid, chatid, MsgData(text=text))
