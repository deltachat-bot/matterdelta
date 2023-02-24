# Matterdelta

[![CI](https://github.com/deltachat-bot/matterdelta/actions/workflows/python-ci.yml/badge.svg)](https://github.com/deltachat-bot/matterdelta/actions/workflows/python-ci.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Matterdelta is a [Matterbridge](https://github.com/42wim/matterbridge) API plugin allowing to connect
Delta Chat group chats to the various chat services supported by Matterbridge.

## Install

```sh
pip install git+https://github.com/deltachat-bot/matterdelta.git
```

### Installing deltachat-rpc-server

This program depends on a standalone Delta Chat RPC server `deltachat-rpc-server` program that must be
available in your `PATH`. To install it check:
https://github.com/deltachat/deltachat-core-rust/tree/master/deltachat-rpc-server

## Usage

Configure the bot's Delta Chat account:

```sh
matterdelta init bot@example.com PASSWORD
# optional:
matterdelta set_avatar "/path/to/avatar.png"
matterdelta config displayname "Bridge Bot"
matterdelta config selfstatus "Hi, I am a Delta Chat bot"
```

Running the bot:

```sh
matterdelta
```

To see all available options run `matterdelta --help`

## Example Configuration

### matterbridge.toml

```
[api]
    [api.deltachat]
    BindAddress="127.0.0.1:4242"
    Token="MATTERBRIDGE_TOKEN"
    Buffer=1000
    RemoteNickFormat="{NICK}"

...

[[gateway]]
name="gateway1"
enable=true

    [[gateway.inout]]
    account="api.deltachat"
    channel="api"

    ...
```

Add these to your existing Matterbridge config to set up an API instance that Matterdelta can connect to.

### config.json

```
{
  "gateways":
  [
    {"gateway": "gateway1", "chat-id": 1234}
  ],
  "api":
  {
    "url": "http://127.0.0.1:4242",
    "token": "MATTERBRIDGE_TOKEN",
  }
}
```

This file should be in Matterdelta's configuration directory, usually `~/.config/matterdelta/`
in Linux-based systems.

To get the `chat-id` of the chat you want to bridge, run the bot and add its address to your group,
then send `/id`in the group, the bot will reply with the chat id, then edit the configuration file
and restart the bot.
