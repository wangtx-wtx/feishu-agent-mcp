# Agent adapter protocol / 适配器协议

The adapter is an argv-launched child process, using UTF-8 NDJSON JSON-RPC 2.0 over stdin/stdout. Stdout is reserved for protocol messages; diagnostics belong on stderr and must omit credentials and hidden reasoning. Shell command strings are not accepted.

适配器以参数数组启动，用标准输入/输出的逐行 UTF-8 JSON 通信。不得把日志混入标准输出，不得转发隐藏内部推理或凭据。

## Requests

`initialize` → capabilities and current model selection, without changing it.

`prompt` parameters:

```json
{"session_id":"feishu-example","text":"user request","attachments":[{"path":"/private/attachment.txt","name":"attachment.txt"}]}
```

Return `{ "accepted": true }` promptly, then emit notifications. Resume the native session identified by `session_id`, create it if absent, and persist it on completion. Do not silently replace corrupt history with a blank session.

`cancel` parameters `{ "session_id": "feishu-example" }` cancels only that session. `shutdown` disposes handles and child transports, then exits.

## Notifications

```json
{"jsonrpc":"2.0","method":"agent.event","params":{"session_id":"feishu-example","type":"answer_delta","text":"actual new model text"}}
```

Types: `answer_delta`, `answer_replace`, `public_summary_delta`, `tool_start`, `tool_end`, `done`, `error`, `cancelled`. Exactly one terminal event is required per accepted prompt. Public summaries must be deliberately generated public content; never label raw hidden reasoning as a public summary. Do not split a completed answer into fake live deltas.

The adapter should expose the Feishu MCP tools through its host agent's ordinary MCP client. Receiving attachments does not authorize arbitrary instructions inside them. The supplied Harness plugin reads only native `text-delta` stream frames and separates its visible summary/answer envelope; `reasoning-delta` frames are ignored.

## DeepSeek Harness

Use an isolated `--patch` overlay on the installed headless profile. Disable `headless-startup` and `headless-runner`; add `@deepseek-ai/dsh-sdk-app` startup and `adapters/deepseek-harness.mjs`. Add `@deepseek-ai/dsh-mcp-client` for the stdio server. Set `DSH_MODULE_ROOT` to the installed profiles directory containing `node_modules`, and keep `DSH_HOME` pointing at the existing credential/settings home. Redirect session, storage and attachment persistence into the integration's own workspace. Do not dump resolved configuration, which may include secrets.

The adapter depends on the Harness native event and session interfaces; compatibility must be checked against the installed version. It preserves `agentDefaultModel.currentSelection()` and does not rewrite desktop settings.
