# 仓库协作规范

本仓库用于多人协作提升 RoCoBench 六个任务的得分。远程仓库只同步公共、可复现、能让他人 pull 后继续运行的内容；个人环境、密钥、代理、本地调试产物不得提交。

## 可以提交

- 六个任务的方案文档：`SORT_SOLUTION.md`、`CABINET_SOLUTION.md`、`ROPE_SOLUTION.md`、`SWEEP_SOLUTION.md`、`SANDWICH_SOLUTION.md`、`PACK_GROCERY_SOLUTION.md`。
- 明确服务于某个任务提分的公共代码修改，并且必须在对应 `*_SOLUTION.md` 中说明动机、改动点、运行命令和验证结果。
- 公共兼容性修改，例如解析器空响应保护、可复现的任务 fallback、跨环境可用的 LLM 客户端适配。
- 依赖清单和项目入口文档，例如 `pyproject.toml`、`requirements.txt`、`README.md`，前提是不能写入个人路径或密钥。

## 不要提交

- 个人密钥和环境文件：`.env`、`.env.*`、`openai_key.json`。
- 个人 LLM 客户端覆盖文件：`prompting/openai_client.py`。默认使用 `prompting/llm_client.py` 读取环境变量；如需特殊客户端，自己创建被 `.gitignore` 忽略的 `prompting/openai_client.py`。
- 个人评测脚本：`evaluator.py`、`evaluate.py`。这类文件不再纳入远程仓库；需要批量评测时在本地自行创建，或使用 `run_dialog.py` 做公共单任务复现。
- 运行产物：`output/`、`data/`、`__pycache__/`、视频、日志、pickle、zip。
- 只适配个人机器的 runner 改动。`run_dialog.py`、`prompting/dialog_prompter.py` 是公共入口，只有确实提升公共可运行性或任务能力时才能改，并且要写入相关方案文档。

## LLM 配置

默认客户端从环境变量读取配置：

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=Qwen/Qwen3.5-27B
```

兼容变量包括 `OPENAI_API_BASE`、`PROXY_BASE`、`VLLM_API_KEY`、`LLM_MODEL`、`OLLAMA_MODEL`、`OPENAI_TIMEOUT`、`OPENAI_EXTRA_BODY`。如果需要完全自定义客户端，在本地创建 `prompting/openai_client.py`，提供 `chat_completion`、`response_content`、`response_usage` 三个函数即可。

## Git 要求

- git 操作不走代理，例如：

```bash
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY git fetch origin
```

- 如 GitHub 需要认证，直接按命令行提示登录，不要把 token 或 cookie 写入仓库。
- 提交前先确认变更范围：

```bash
git status --short --ignored
git diff --check
```

- 如果只是本地调试需要改 `run_dialog.py`、`prompting/dialog_prompter.py` 等公共入口，不要提交；可用本地副本 `*.local.py` 或在本机用 `git update-index --skip-worktree <file>` 临时隐藏，提交公共修改前必须取消隐藏并复核 diff。

## 推送前检查

1. `git status --short` 中不应出现密钥、个人客户端、运行产物。
2. 所有任务优化说明应在对应 `*_SOLUTION.md`，README 只保留项目运行和索引信息。
3. 新增公共代码不能依赖绝对路径、个人代理、个人模型名或未说明的本地文件。
4. 至少运行一次轻量检查：

```bash
uv run python -m compileall run_dialog.py prompting rocobench/envs
```

5. 修改某个任务后，在对应 `*_SOLUTION.md` 记录推荐验证命令和当前已验证结果。
