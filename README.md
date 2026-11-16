# 小宠百问 · H5

异宠（爬宠 / 鸟 / 小型哺乳 / 水族）饲养问答智能体：问答、物种图鉴、合规速查、附近异宠医院、饲养日志。

## 部署

本仓库带 `render.yaml`，在 Render 里 **New → Blueprint** 选这个仓库即可。密钥不写进仓库，用环境变量注入：

| 变量 | 说明 |
|---|---|
| `LLM_API_KEY` | 大模型 Key（DeepSeek 等） |
| `SESSION_SECRET` | 会话签名密钥，建议随机 32 位 |
| `XC_ADMIN_PASSWORD` | 后台 `/admin` 密码 |
| `XC_SUPPORT` / `XC_SUPPORT_HOURS` | 客服电话与时间，可空 |

也可以直接 `docker build -t xiaochong . && docker run -p 8080:8080 -e PORT=8080 -e LLM_API_KEY=sk-xxx xiaochong`。

## 结构

- `main.py` 入口（FastAPI），`/api/health` 健康检查
- `static/` 前端资源；图鉴图片打包在 `static/dex.zip`，由 `/static/dex/{path}` 读取
- `data/` 知识库、图鉴、合规、地区等静态数据

## 注意

免费容器的磁盘是临时的，重新部署会清空 `data/` 下的用户数据；知识库与图鉴在镜像里，不受影响。
