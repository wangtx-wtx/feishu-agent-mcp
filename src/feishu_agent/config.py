import json, os, pathlib, secrets
from dataclasses import dataclass, field

def private_dir():
    return pathlib.Path(os.environ.get("FEISHU_AGENT_HOME", pathlib.Path.home()/".feishu-agent"))

@dataclass
class Config:
    app_id: str = ""
    app_secret: str = field(default="", repr=False)
    owner_open_id: str = ""
    api_base: str = "https://open.feishu.cn"
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    allowed_roots: list[str] = field(default_factory=list)
    adapter_command: list[str] = field(default_factory=list)
    adapter_env: dict[str,str] = field(default_factory=dict, repr=False)
    adapter_cwd: str = ""
    state_dir: str = ""
    port: int = 8766
    pairing_code: str = field(default_factory=lambda: secrets.token_urlsafe(12), repr=False)
    stream_interval: float = 0.7
    public_summary: bool = True

    @classmethod
    def load(cls, path=None):
        path=pathlib.Path(path or private_dir()/"config.json")
        value=cls(**json.loads(path.read_text(encoding="utf-8")))
        if not value.state_dir: value.state_dir=str(path.parent/"state")
        return value

    def save(self, path=None):
        from dataclasses import asdict
        path=pathlib.Path(path or private_dir()/"config.json")
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(".next");tmp.write_text(json.dumps(asdict(self),ensure_ascii=False,indent=2),encoding="utf-8")
        os.chmod(tmp,0o600);os.replace(tmp,path)
        if os.name=="nt":
            import subprocess
            user=os.environ.get("USERNAME","")
            if user: subprocess.run(["icacls",str(path),"/inheritance:r","/grant:r",user+":F","SYSTEM:F"],capture_output=True,check=True)

    def file_bytes(self, filename):
        p=pathlib.Path(filename)
        if p.is_symlink(): raise ValueError("FILE_SYMLINK_DENIED")
        resolved=p.resolve(strict=True)
        roots=[pathlib.Path(r).resolve(strict=True) for r in self.allowed_roots]
        if not any(resolved.is_relative_to(r) for r in roots):raise ValueError("FILE_OUTSIDE_ALLOWED_ROOTS")
        if not resolved.is_file():raise ValueError("FILE_NOT_REGULAR")
        if resolved.stat().st_size>30*1024*1024:raise ValueError("FILE_TOO_LARGE")
        data=resolved.read_bytes()
        if len(data)>30*1024*1024:raise ValueError("FILE_TOO_LARGE")
        return resolved,data
