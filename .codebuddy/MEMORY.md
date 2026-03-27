# KarvisForYou 项目长期记忆

## 一、服务器信息

| 项目 | 值 |
|---|---|
| 云服务商 | 腾讯云 Lighthouse |
| 服务器 IP | 193.112.94.141 |
| SSH 端口 | 22 |
| 操作系统 | Ubuntu Server 22.04 LTS 64bit |
| SSH 登录用户 | ubuntu（通过公钥认证，无需密码） |
| 实际操作用户 | root（ubuntu 用户通过 sudo 执行） |
| 服务端口 | 9000（Flask） |

## 二、项目部署架构

| 项目 | 值 |
|---|---|
| 部署方式 | Docker + docker-compose |
| 服务器项目路径 | `/root/KarvisForYou` |
| docker-compose 路径 | `/root/KarvisForYou/deploy/docker-compose.yml` |
| Dockerfile 路径 | `/root/KarvisForYou/deploy/Dockerfile` |
| Docker 容器名 | `karvis` |
| Docker 镜像名 | `deploy_karvis` |
| 端口映射 | 9000:9000 |
| 数据持久化 | Docker volume `karvis_data` → 容器内 `/app/data` |
| 健康检查 | 每 30s 检查 `http://localhost:9000/web/login` |

### ⚠️ 重要注意事项
- **服务器无法直连 GitHub**（国内网络限制），不能用 `git pull`，必须从本地 scp 传文件
- 服务器 git remote 指向 `sameencai/KarvisForYou`（原始仓库），本地指向 `renardbebe/KarvisForYou`（fork），**两个不同仓库**，不要在服务器上执行 git 操作
- 源码在 docker build 时 COPY 进镜像（`COPY src/ ./src/`），修改文件后**必须 rebuild 镜像**，不能只 restart
- 数据（用户配置、记忆、笔记等）在 volume 中持久化，rebuild **不会丢失数据**

## 三、部署更新 SOP（标准操作流程）

### 前置条件
- 本地代码已测试/review 完毕
- 已 git commit + push 到远程仓库（可选但建议）

### Step 1: 传输文件到服务器

将修改的文件 scp 到服务器 `/tmp` 目录：

```bash
# 在本地项目根目录执行
# 示例：传 src/ 下的文件
cd /Users/renardbebe/AiProjects/KarvisForYou

scp src/app.py src/brain.py ubuntu@193.112.94.141:/tmp/

# 如果有 skills/ 子目录下的文件，也传到 /tmp
scp src/skills/settings.py ubuntu@193.112.94.141:/tmp/

# 如果有新文件（如新 skill），同样 scp 到 /tmp
scp src/skills/new_skill.py ubuntu@193.112.94.141:/tmp/
```

**说明**：所有文件都先传到 `/tmp`，因为 ubuntu 用户无法直接写入 `/root/` 目录。

### Step 2: 复制文件到项目目录 + 重建容器

**一条命令完成所有操作**（推荐）：

```bash
ssh ubuntu@193.112.94.141 "sudo bash -c '
  # 复制 src/ 根目录下的文件
  cp /tmp/app.py /tmp/brain.py /tmp/prompts.py /root/KarvisForYou/src/

  # 复制 skills/ 子目录下的文件
  cp /tmp/settings.py /root/KarvisForYou/src/skills/

  # 重建并启动容器
  cd /root/KarvisForYou/deploy && \
  docker-compose down && \
  docker-compose build --no-cache && \
  docker-compose up -d
'"
```

**关键**：
- 必须用 `sudo bash -c '...'` 包裹整个命令，因为项目在 `/root/` 下
- `docker-compose build --no-cache` 确保使用最新代码
- 根据实际修改的文件调整 cp 命令，只复制本次修改的文件

### Step 3: 验证部署

```bash
# 1. 检查容器状态（等 15-30 秒让健康检查通过）
ssh ubuntu@193.112.94.141 "sudo docker ps --filter name=karvis --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"
# 期望输出: karvis    Up XX seconds (healthy)    0.0.0.0:9000->9000/tcp

# 2. 查看启动日志
ssh ubuntu@193.112.94.141 "sudo docker logs karvis 2>&1 | tail -20"
# 期望看到: [Scheduler][V8] 已启动 N 个任务

# 3. 验证特定 skill 是否注册（可选）
ssh ubuntu@193.112.94.141 "sudo docker exec karvis python -c \"
from skills.settings import SKILL_REGISTRY
print('settings skills:', list(SKILL_REGISTRY.keys()))
\""

# 4. 验证总 skill 数量（可选）
ssh ubuntu@193.112.94.141 "sudo docker exec karvis python -c \"
from brain import _load_all_skills
skills = _load_all_skills()
print(f'Total skills: {len(skills)}')
\""
```

### 常见问题排查

| 问题 | 排查命令 | 解决方案 |
|---|---|---|
| 容器 Exited | `sudo docker logs karvis 2>&1 \| tail -50` | 查看报错，通常是 Python import 错误 |
| 容器 unhealthy | `sudo docker exec karvis curl -s http://localhost:9000/web/login` | Flask 没启动成功，查日志 |
| SSH 连接失败 | `ssh -v ubuntu@193.112.94.141` | 检查公钥，必要时通过腾讯云 VNC 登录修复 |
| scp 超时 | 检查本地网络 | 服务器在腾讯云深圳区域 |
| build 超时/失败 | `sudo docker-compose build --no-cache 2>&1` | 可能是 pip install 网络问题，重试即可 |

## 四、项目技术架构

| 项目 | 值 |
|---|---|
| 语言/框架 | Python 3.11 / Flask |
| 监听端口 | 9000 |
| LLM 模型 | DeepSeek V3.2（主）/ Qwen（搜索）/ Flash（轻量判断） |
| 定时任务 | 内置 APScheduler + 腾讯云 SCF 外部调度器 |
| 用户渠道 | 企业微信（wework） |
| 数据存储 | 本地文件系统（JSON + Markdown），无数据库 |

### 代码结构

```
src/
├── app.py              # Flask 入口 + 定时任务 + 消息处理主流程
├── brain.py            # LLM 路由决策 + Skill 分发 + Agent Loop
├── prompts.py          # System Prompt 构建（RULES/SOUL/FORMAT）
├── config.py           # 全局配置常量
├── memory.py           # 用户记忆/状态读写
├── skills/             # Skill 模块目录（每个 .py 通过 SKILL_REGISTRY 注册）
│   ├── settings.py     # 用户设置（昵称/风格/信息/频率等）
│   ├── todo_manage.py  # 待办管理
│   ├── weather_query.py # 天气查询
│   ├── web_search.py   # 联网搜索
│   ├── book_notes.py   # 读书笔记
│   └── ...
├── web_static/         # Web 前端页面（HTML）
└── .env                # 环境变量（API Keys 等，不入 git）
```

### Skill 开发要点
- 每个 skill 是 `src/skills/` 下的独立 `.py` 文件
- 必须暴露 `SKILL_REGISTRY = {"skill.name": handler_func}` 字典
- handler 签名: `def handler(params, state, ctx)` → 返回 `{"success": bool, "reply": str, ...}`
- 注册新 skill 后需在以下位置同步更新：
  1. `prompts.py` — `SKILL_PROMPT_LINES` 添加描述 + `RULES_*` 添加路由规则
  2. `brain.py` — 根据需要加入 `_NO_REROUTE_SKILLS` / `_SKIP_NOTE_SKILLS` / `_SIMPLE_SKILLS` 等集合

## 五、Git 仓库信息

| 项目 | 值 |
|---|---|
| 本地仓库 | `/Users/renardbebe/AiProjects/KarvisForYou` |
| 远程仓库 | `git@github.com:renardbebe/KarvisForYou.git`（fork） |
| 原始仓库 | `sameencai/KarvisForYou` |
| 主分支 | main |

### Git + Deploy 标准工作流

```
1. 本地开发修改代码
2. git add + git commit + git push origin main
3. 按「部署更新 SOP」执行 scp → cp → rebuild
4. 验证容器 healthy
```
