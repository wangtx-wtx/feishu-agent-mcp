"""Loopback-only setup form. Secrets never echo back to HTML or logs."""
import secrets,json,pathlib,html
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import HTMLResponse,JSONResponse
from .config import Config,private_dir
from .cli import GUIDE,SCOPES

def app(path=None,port=8767):
    application=FastAPI();nonce=secrets.token_urlsafe(32)
    path=pathlib.Path(path or private_dir()/'config.json')
    @application.middleware('http')
    async def local(request,call_next):
        if request.headers.get('host') not in (f'127.0.0.1:{port}',f'localhost:{port}'):return JSONResponse({'error':'HOST_DENIED'},403)
        if request.headers.get('origin') not in (None,f'http://127.0.0.1:{port}',f'http://localhost:{port}'):return JSONResponse({'error':'ORIGIN_DENIED'},403)
        response=await call_next(request);response.headers['Cache-Control']='no-store';response.headers['Content-Security-Policy']="default-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'";return response
    @application.get('/setup',response_class=HTMLResponse)
    async def setup():
        steps=''.join(f'<li><a href="{html.escape(url)}" target="_blank" rel="noreferrer">{html.escape(title)}</a><p>{html.escape(detail)}</p></li>' for title,url,detail in GUIDE)
        return f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Feishu Agent MCP · 接入向导</title>
        <style>body{{max-width:900px;margin:40px auto;padding:0 24px;font:16px/1.7 system-ui;color:#172d3c;background:#f5f8f9}}h1{{font-size:28px}}form{{background:white;padding:24px;border:1px solid #ccd7df}}label{{display:block;margin:14px 0}}input,textarea{{display:block;width:95%;padding:10px;border:1px solid #aabac8}}button{{padding:12px 24px;background:#174d67;color:white;border:0}}pre{{white-space:pre-wrap}}</style>
        <h1>Feishu Agent MCP · 接入向导</h1><p>One bot · One agent · One owner / 一个机器人、一个Agent、一个用户</p><ol>{steps}</ol>
        <details><summary>权限导入 JSON / Permission JSON</summary><pre>{html.escape(json.dumps(SCOPES,indent=2))}</pre></details>
        <h2>本机私有配置 / Private local configuration</h2><p>凭据不发给模型，不上传GitHub。Credentials stay local and private.</p>
        <form method="post" action="/setup"><input type="hidden" name="csrf" value="{nonce}">
        <label>App ID<input name="app_id" required autocomplete="off"></label>
        <label>App Secret<input name="app_secret" type="password" required autocomplete="off"></label>
        <label>允许发送文件的目录 / Allowed roots (one per line)<textarea name="roots" required></textarea></label>
        <label>Agent 工作目录 / Working directory<input name="cwd"></label>
        <label>适配器命令JSON数组 / Adapter argv JSON<textarea name="command">[]</textarea></label>
        <label>适配器环境JSON / Adapter environment JSON<textarea name="environment">{{}}</textarea></label>
        <button type="submit">保存到本机 / Save locally</button></form></html>'''
    @application.post('/setup',response_class=HTMLResponse)
    async def save(request:Request):
        form=await request.form()
        if not secrets.compare_digest(str(form.get('csrf','')),nonce):raise HTTPException(403)
        c=Config.load(path) if path.exists() else Config()
        c.app_id=str(form['app_id']).strip();c.app_secret=str(form['app_secret']).strip()
        c.allowed_roots=[str(pathlib.Path(r).resolve()) for r in str(form['roots']).splitlines() if r.strip()]
        c.adapter_cwd=str(form['cwd']);c.adapter_command=json.loads(form['command']);c.adapter_env=json.loads(form['environment']);c.state_dir=str(path.parent/'state')
        if not isinstance(c.adapter_command,list) or not all(isinstance(x,str) for x in c.adapter_command):raise HTTPException(400,'Command must be argv array')
        if not c.app_id or not c.app_secret:raise HTTPException(400,'Credentials required')
        if not isinstance(c.adapter_env,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in c.adapter_env.items()):raise HTTPException(400,'Environment must contain string values')
        c.save(path)
        return '<h1>配置已保存 / Configuration saved</h1><p>凭据不会在此显示。启动serve，再继续长连接配置、发布和配对。</p>'
    return application
