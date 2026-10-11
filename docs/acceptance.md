# Live acceptance / 真实验收

Validated on 2026-10-11 with the locally installed DeepSeek Harness (dsh 0.1.5-rc.1, SDK app 0.1.5-rc.2), `deepseek-official / deepseek-flash`, and a newly created dedicated Feishu custom bot.

已使用本机 DeepSeek Harness 和全新独立飞书机器人实测，未用模拟入站代替真实私聊。

- Official Feishu console verified the live long connection; application published for one owner.
- A real user-side private message paired the owner and received the bot acknowledgement.
- Chinese private messages invoked the native agent and returned a streaming card with a collapsible public processing summary.
- A UTF-8 test file was uploaded through Feishu Web, downloaded by the bridge, and accurately read by the agent. Its received SHA256 equalled the local fixture hash.
- Standard MCP discovery returned exactly `send_message` and `send_file`. Both produced actual Feishu receipts; repeating the same request IDs returned the same receipts without a duplicate send.
- The Harness model itself invoked both tools successfully, including sending the requested local file.
- A final native-stream-to-card test recorded actual answer element updates before the terminal `done` event, including a 1-character update followed by 262 characters. This was not completed text split into artificial chunks.
- `/clear` acknowledged a new context while retaining attachments and conversation history.
- Source and distribution packages were compared against the actual private App Secret, bearer token and pairing code: no matches.

文件验收 SHA256：`90987b69910fcf0006ae492fb89789f7c1117b5ab928778d0d226c4e9e2f67da`。

The automated tests separately exercise allowed file roots, duplicate sends, uncertain delivery refusal, key conflicts, interruption recovery, control-message isolation and the CardKit element endpoint. These use simulated HTTP and are not the live tests above.

Boundaries: only this Harness version and this Feishu environment received live acceptance. Linux CI, other agent adapters, image interpretation, cancellation during a long tool operation, and unattended long-term operation are not claimed as live-tested. Hidden model reasoning is not a supported export.
