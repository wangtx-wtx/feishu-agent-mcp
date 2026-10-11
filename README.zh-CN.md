# Feishu Agent MCP

[English](README.md) · [适配器协议](docs/adapter-protocol.md)

为 Agent 提供主动调用飞书通道的标准能力，同时支持从飞书私聊 Agent。一个机器人、一个 Agent、一个配对用户，无需预先建立上传或对话通道。

## 功能

- 仅两个 MCP 工具：`send_message(text, request_id?)`、`send_file(path, request_id?)`。
- 飞书长连接接收单聊文字、文件和图片；附件下载后交给 Agent 读取。
- 保持原生会话；`/new` 或 `/clear` 开新会话，`/stop` 取消当前回复。清除上下文不会删除材料或历史会话。
- 真实回答增量通过 CardKit 流式更新显示。折叠面板展示公开处理摘要，随附适配器不会输出模型隐藏内部思维链。
- 入站去重、发送幂等和持久记录；无法确定是否已送达时不自动重发。
- 本机配置向导及 DeepSeek Harness 适配器；其它 Agent 按协议接入。保留原有模型选择和普通会话设置。

MCP 工具负责发送。飞书入站消息要触发 Agent 的原生会话接口，必须配置接收桥接适配器；单独注册 MCP 不会使宿主自动接收新的用户回合。

## 安装与完整接入

需要 Python 3.11 或以上。在项目目录创建并激活虚拟环境：

```sh
python -m venv .venv
python -m pip install -e .
feishu-agent wizard
```

打开 `http://127.0.0.1:8767/setup`，向导含全部步骤及官方链接。

1. 在[飞书开放平台](https://open.feishu.cn/app)创建企业自建应用，添加「机器人」能力。使用专用应用，避免多个程序争抢同一个长连接。
2. 从「凭证与基础信息」把 App ID、App Secret 填入本机向导。保存位置为 `~/.feishu-agent/config.json`，不在仓库里。不要向模型发送密钥。
3. 进入「权限管理→批量导入」，运行 `feishu-agent permissions` 获取权限 JSON，导入并申请开通。包括以机器人发送消息、读取单聊消息、获取与上传图片及文件、创建和更新卡片。
4. 启动 `feishu-agent serve`。在「事件与回调」选择长连接，验证成功后保存；按应用身份添加 `im.message.receive_v1`「接收消息」事件。
5. 创建应用版本，设置可用范围并发布。可能需要企业管理员审批。配置页面的勾选不等于权限已生效，也不等于真实验收通过。
6. 本机运行 `feishu-agent pairing`，在飞书搜索机器人并私聊发送显示的 `/pair ...`。首次有效配对绑定唯一用户，群聊和其它用户不会触发 Agent。
7. 向导中填写适配器命令 JSON 数组、工作目录，并给 Agent 添加 MCP 配置。Python 必须使用虚拟环境的绝对路径。

```json
{
  "mcpServers": {
    "feishu": {
      "command": "C:/path/to/.venv/Scripts/python.exe",
      "args": ["-m", "feishu_agent.cli", "mcp"]
    }
  }
}
```

`serve` 需要持续运行。stdio MCP 向本机服务转发请求，不额外占用飞书长连接。自定义配置路径放在子命令之前：`feishu-agent --config /private/config.json serve`。另支持带私有 bearer token 的本机 Streamable HTTP MCP。

## 验收与边界

`doctor` 检查凭据和配置，不能证明双向聊天已通过。必须从真实飞书私聊发消息，观察结束前的增量回复，上传测试附件并确认读取，再让 Agent 分别调用发送消息、发送文件；核对文件 SHA256 和重复 request_id 无重复发送。

```sh
python -m pip install -e '.[test]'
python -m pytest -q
```

自动测试使用模拟 HTTP，不能替代实测。卡片失败会明确提示降级并发送最终结果，不伪造流式效果。初版接收文字、文件、图片；语音转写和富文本消息解析不在此范围。

服务仅监听本机，发送文件限制在允许目录内，单文件上限 30 MiB。请勿直接暴露配置向导或服务到公网。附件内的指令不构成用户授权；原生 Agent 自身的文件权限与审批策略仍需由运行者设置。

MIT 开源许可。
