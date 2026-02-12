"""
Google OAuth2 本地授权脚本
在 Mac 宿主机上运行，完成浏览器授权后生成 token 文件。
token 通过 Docker volume 挂载自动共享给容器。

用法：python3 scripts/google_auth.py
"""

import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent

# 确保依赖可用
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("缺少依赖，正在安装...")
    import subprocess
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "google-api-python-client", "google-auth", "google-auth-oauthlib"
    ])
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

credentials_path = ROOT / "config" / "google_credentials.json"
token_path = ROOT / "data" / ".google_token.json"

if not credentials_path.exists():
    print(f"❌ 凭据文件不存在: {credentials_path}")
    print("请从 Google Cloud Console 下载 OAuth2 Client ID JSON 文件")
    sys.exit(1)

creds = None

# 尝试加载已有 token
if token_path.exists():
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        print(f"✅ 已加载缓存 token: {token_path}")
    except Exception as e:
        print(f"⚠️ 缓存 token 无效: {e}")
        creds = None

# 刷新或重新授权
if creds and creds.expired and creds.refresh_token:
    try:
        creds.refresh(Request())
        print("✅ Token 已刷新")
    except Exception:
        creds = None

if not creds or not creds.valid:
    print("🔐 即将打开浏览器进行 Google 授权...")
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=8099, open_browser=True)
    print("✅ 授权成功！")

# 保存 token
token_path.parent.mkdir(parents=True, exist_ok=True)
with open(token_path, "w") as f:
    f.write(creds.to_json())

print(f"✅ Token 已保存到: {token_path}")
print("Docker 容器通过 volume 挂载可直接使用此 token，无需再次授权。")
