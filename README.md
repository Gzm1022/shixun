# RocoBench 协作仓库

本仓库用于多人协作提升 RoCoBench 六个任务的执行成功率。README 只保留公共运行方式和任务文档索引；各任务的优化细节、验证命令和结果记录在对应的 `*_SOLUTION.md` 中。

## 环境准备

本项目使用 `uv` 管理 Python 环境，并通过 `.python-version` 固定 Python 3.8。

首次运行前执行：

```bash
uv sync
```

之后可以使用 `run_dialog.py` 运行单个任务：

```bash
uv run python run_dialog.py --task sort --comm_mode plan --num_runs 1 --tsteps 3 --skip_display --run_name sort_smoke
```

第一次执行 `uv sync` 时，`uv` 会创建 `.venv` 虚拟环境；如果本机没有兼容的 Python 3.8，也会自动下载对应解释器。

## 输出目录

`run_dialog.py` 默认把运行产物写入 `data/<run_name>/`：

```text
data/<run_name>/
|-- args_YYYYMM_HHMM.json
`-- run_0/
    |-- step_0/
    |-- steps*_success_*.json
    `-- *.html / *.mp4
```

`data/`、`output/`、视频、日志和中间 pickle 都是本地产物，已被 `.gitignore` 忽略。

## LLM 配置

默认通过环境变量配置 OpenAI-compatible 接口：

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=Qwen/Qwen3.5-27B
```

如需个人化客户端，可在本地创建被 `.gitignore` 忽略的 `prompting/openai_client.py`。公共代码默认使用 `prompting/llm_client.py`，没有个人覆盖文件时也能直接运行。

## 任务方案

- [Sort](SORT_SOLUTION.md)
- [Cabinet](CABINET_SOLUTION.md)
- [Rope](ROPE_SOLUTION.md)
- [Sweep](SWEEP_SOLUTION.md)
- [Sandwich](SANDWICH_SOLUTION.md)
- [Pack Grocery](PACK_GROCERY_SOLUTION.md)

## 评测入口

远程仓库不再维护 `evaluator.py` / `evaluate.py`，这类批量评测脚本按个人环境本地创建并被 `.gitignore` 忽略。公共复现入口是 `run_dialog.py`；任务相关推荐命令写在对应的 `*_SOLUTION.md` 中。

## 单任务运行

直接运行单个 rollout：

```bash
uv run python run_dialog.py --task sort --comm_mode plan --num_runs 1 --tsteps 8 --num_replans 2 --skip_display --skip_smooth_path --fallback_first --run_name sort_debug
```

运行结果会保存在：

```text
data/sort_debug/
```

批量评测如需汇总多个任务，可在本地创建被忽略的 `evaluator.py` 调用这些命令，不要提交到远程仓库。

## 协作规则

提交前请阅读 [AGENTS.md](AGENTS.md)。远程仓库不得包含个人密钥、代理配置、运行产物、个人 LLM 客户端或只适配单人环境的 runner/evaluator 改动。

## pack_code.sh 使用方法

`pack_code.sh` 用于按照 `.gitignore` 规则打包当前工作区。

```bash
# 使用默认文件名 code_YYYYMMDD_HHMMSS.zip
./pack_code.sh

# 指定输出文件名
./pack_code.sh myproject.zip

# 未写 .zip 后缀时会自动补全
./pack_code.sh myproject
```

如果脚本没有执行权限，先运行：

```bash
chmod +x pack_code.sh
```

## 注意事项

- 本项目默认使用 `uv run` 启动 Python 脚本。
- 使用本地 Ollama 模型时，需要提前确认模型已经拉取并启动服务。
- 任务相关优化、风险和验证结果统一记录在对应 `*_SOLUTION.md` 中。
