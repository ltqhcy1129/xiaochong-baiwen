"""PythonAnywhere 启动包装。

免费账号的出站请求只能走 proxy.server:3128 这个代理，且只放行白名单域名
（DeepSeek / OpenAI / Anthropic 等已在白名单里）。httpx 默认 trust_env=True，
所以只要把代理写进环境变量即可，业务代码一行都不用改。

启动命令用 pa_app:app 而不是 main:app。
本地 / WorkBuddy 环境没有 PA_DOMAIN，这段不会生效。
"""

import os

if os.environ.get("PA_DOMAIN") or os.environ.get("PA_USERNAME"):
    _proxy = "http://proxy.server:3128"
    for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
               "http_proxy", "https_proxy", "all_proxy"):
        os.environ.setdefault(_k, _proxy)

from main import app  # noqa: E402,F401
