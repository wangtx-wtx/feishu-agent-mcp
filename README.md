# Feishu Agent MCP

[中文文档](README.zh-CN.md) · [Adapter protocol](docs/adapter-protocol.md)

Give an agent a standard Feishu channel: send messages, send files, and receive private conversations with real answer streaming. One bot, one agent, one paired owner. No existing channel is required.

## What it provides

- Exactly two MCP tools: `send_message(text, request_id?)` and `send_file(path, request_id?)`.
- Feishu long connection for incoming private text, file and image messages.
- Persistent native agent sessions; `/new` or `/clear` starts a new conversation, `/stop` cancels the active response.
- Actual answer deltas rendered through CardKit streaming updates. An optional collapsible panel contains a **public processing summary**. Hidden internal reasoning is never exported by the included adapter.
- Durable inbound deduplication and outbound idempotency. Uncertain deliveries are never automatically resent.
- Local onboarding wizard and a DeepSeek Harness adapter. Other agents integrate through the small documented adapter protocol.

MCP alone cannot start a host agent's turn. The receiving bridge invokes an adapter that speaks the agent's native session API. Sending tools work independently; bidirectional chat requires a configured adapter. No model selection or existing profile is rewritten.

## Install

Python 3.11+:

```sh
python -m venv .venv
# Activate the environment for your platform.
python -m pip install -e .
feishu-agent wizard
```

Open `http://127.0.0.1:8767/setup`. Credentials are stored in `~/.feishu-agent/config.json`, outside the repository. Windows config permissions are restricted to the current user and SYSTEM; POSIX uses mode 600. Configure only directories the agent may send files from.

## Complete Feishu onboarding

1. In [Feishu Open Platform](https://open.feishu.cn/app), create a custom application. Enable **Bot** under application capabilities. Use a dedicated app; multiple receivers must not compete for its long connection.
2. Copy its App ID and App Secret into the local wizard. Do not put credentials in an agent prompt, issue or repository.
3. Open **Permission Management → Batch Import**. Run `feishu-agent permissions`, import the JSON, and apply all listed permissions. These cover sending as the bot, receiving private messages, reading/uploading resources, and creating/updating cards.
4. Start `feishu-agent serve`. Under **Events and Callbacks**, choose **long connection**, verify it succeeds, save, and subscribe to `im.message.receive_v1` using application identity.
5. Under **Version Management and Release**, create a version, set an appropriate availability range, and publish. Administrator approval may be required. Unpublished permission changes are not acceptance evidence.
6. Run `feishu-agent pairing` locally. Find your bot in Feishu and send the displayed `/pair ...` command in a private chat. The first valid pairing binds the owner; other senders and group chats are rejected.
7. Configure an agent adapter argv and its working directory in the wizard. Add the following MCP server to the agent, using the environment's absolute Python path:

```json
{
  "mcpServers": {
    "feishu": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "feishu_agent.cli", "mcp"]
    }
  }
}
```

Keep `serve` running: it is the sole owner of the Feishu connection and delivery ledger. Stdio MCP forwards authenticated requests to it. `--config /private/path/config.json` can be placed before the CLI subcommand. Streamable HTTP is also available at `http://127.0.0.1:8766/mcp/` with the private bearer token; do not put that token in public examples.

## Verify

`feishu-agent doctor` checks authentication and basic configuration, **not** complete dialogue. Acceptance requires sending a real private message, observing streamed text before completion, uploading a test attachment and checking the agent reads it, and asking the agent to invoke each outgoing MCP tool. Compare file hashes and confirm a repeated request ID does not send a duplicate.

```sh
python -m pip install -e '.[test]'
python -m pytest -q
```

Automated tests use simulated HTTP responses for safety and are distinguished from live acceptance.

## Boundaries

Services bind to loopback, check browser origins, and require a bearer token for broker requests. Do not expose the broker or wizard directly to the Internet. File sending is limited to configured roots and 30 MiB. Received files are untrusted data, not instructions. A native agent can have broader filesystem permissions than this bridge; its own sandbox and approval policy remain the operator's responsibility.

Streaming requires genuine adapter deltas and working CardKit permissions. On card failure, the bridge explicitly acknowledges the fallback and sends the completed answer; it does not pretend a completed response is a live stream. Incoming text/file/image are supported; voice transcription and rich-post parsing are outside this initial scope.

MIT License.
