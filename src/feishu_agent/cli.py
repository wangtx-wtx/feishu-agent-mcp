import argparse,asyncio,json,getpass,pathlib,sys,webbrowser
from .config import Config,private_dir

SCOPES={'scopes':{'tenant':['im:message:send_as_bot','im:message.p2p_msg:readonly','im:message:readonly','im:resource','cardkit:card:write','cardkit:card:read'],'user':[]}}
GUIDE=[
('创建应用 / Create app','https://open.feishu.cn/app','创建自建应用并启用机器人 / Create a custom app and enable Bot.'),
('配置凭据 / Credentials','https://open.feishu.cn/app','填写 App ID 和 App Secret；只保存到本机受保护配置 / Save credentials only in private local config.'),
('权限 / Permissions','https://open.feishu.cn/document/server-docs/im-v1/message/create','批量导入向导提供的权限JSON，覆盖消息收发、资源读取上传和卡片流式更新 / Import the supplied permission JSON.'),
('事件 / Events','https://open.feishu.cn/document/server-docs/event-subscription-guide/overview','先启动 serve，再选择长连接并订阅 im.message.receive_v1 / Start serve, choose long connection, subscribe receive message.'),
('发布 / Publish','https://open.feishu.cn/document/home/intro-to-custom-app-review','配置应用可用范围，创建版本并发布；必要时由管理员审批 / Set availability and publish; admin approval may be required.'),
('绑定 / Pair','https://open.feishu.cn/app','在飞书私聊机器人发送本机 pairing 输出的一次性配对指令 / Send the one-time pairing command in a private bot chat.'),
('连接 Agent / Connect agent','https://github.com/deepseek-ai/deepseek-harness','配置适配器命令和 MCP；doctor只检查配置与可达性，验收必须使用真实消息 / Configure adapter and MCP; verify with actual messages.')]

async def doctor(c):
    from .store import Store
    from .feishu import Feishu
    f=Feishu(c,Store(c.state_dir))
    try:
        await f.token();bot=await f.api('GET','bot/v3/info');print(json.dumps({'credentials':True,'bot_enabled':bool(bot),'owner_configured':bool(c.owner_open_id or f.store.get('owner')),'adapter_command_configured':bool(c.adapter_command),'real_dialogue_verified':False},ensure_ascii=False))
    finally:await f.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--config');s=p.add_subparsers(dest='command',required=True)
    s.add_parser('setup');s.add_parser('wizard');s.add_parser('guide');s.add_parser('permissions');s.add_parser('pairing');s.add_parser('doctor');s.add_parser('serve');s.add_parser('mcp')
    args=p.parse_args()
    if args.command=='wizard':
        import uvicorn
        from .wizard import app
        print('Open http://127.0.0.1:8767/setup / 打开本机接入向导')
        uvicorn.run(app(args.config),host='127.0.0.1',port=8767,access_log=False);return
    if args.command=='permissions':print(json.dumps(SCOPES,indent=2));return
    if args.command=='guide':
        for i,(title,url,detail) in enumerate(GUIDE,1):print(f'{i}. {title}\n{url}\n{detail}\n')
        return
    if args.command=='setup':
        path=pathlib.Path(args.config or private_dir()/'config.json');c=Config.load(path) if path.exists() else Config()
        print('Credentials are private; do not paste them into agent chats. / 凭据仅保存到本机，不要发送到聊天。')
        c.app_id=input('App ID: ').strip();c.app_secret=getpass.getpass('App Secret: ').strip()
        c.allowed_roots=[str(pathlib.Path(r.strip()).resolve()) for r in input('Allowed file directories, separated by ; / 文件目录，用;分隔: ').split(';') if r.strip()]
        c.adapter_cwd=input('Agent working directory / 工作目录: ').strip()
        command=input('Adapter argv JSON / 适配器命令JSON数组（仅发送可留空）: ').strip();c.adapter_command=json.loads(command) if command else []
        c.state_dir=str(path.parent/'state');c.save(path);print('Saved protected config. Run guide, serve, then pairing. / 已保存，继续guide、serve及pairing。');return
    c=Config.load(args.config)
    if args.command=='pairing':print('/pair '+c.pairing_code);return
    if args.command=='doctor':asyncio.run(doctor(c));return
    if args.command=='mcp':
        from .mcp_stdio import run
        run(args.config);return
    if args.command=='serve':
        import uvicorn
        from .server import app
        uvicorn.run(app(c,args.config),host='127.0.0.1',port=c.port,access_log=False)

if __name__=='__main__':main()
