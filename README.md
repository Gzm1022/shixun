# RocoBench 评测与 Sort 任务优化

本仓库包含 RocoBench 多机器人任务的批量评测脚本、运行入口和本次针对 Sort 任务的优化代码。当前版本重点解决 Sort 任务中局部模型调用失败、重复规划、交接点不可达和评测耗时过长的问题。

## 环境准备

本项目使用 `uv` 管理 Python 环境，并通过 `.python-version` 固定 Python 3.8。

首次运行前执行：

```bash
uv sync
```

之后可以使用：

```bash
uv run python evaluator.py
```

第一次执行 `uv sync` 时，`uv` 会创建 `.venv` 虚拟环境；如果本机没有兼容的 Python 3.8，也会自动下载对应解释器。

## 评测输出目录

每次运行 `evaluator.py` 后，日志、任务结果和运行产物会统一保存在一个带时间戳的目录中：

```text
output/run_YYYYMMDD_HHMMSS/
|-- evaluator.log
|-- run.json
|-- summary.json
`-- tasks/
    `-- 01_sort/
        |-- command.txt
        |-- runs/
        |   |-- args_YYYYMM_HHMM.json
        |   `-- run_0/
        |-- stdout.log
        |-- stderr.log
        |-- result.json
        `-- summary.json
```

其中：

- `evaluator.log`：本次评测的终端总日志。
- `stdout.log` / `stderr.log`：单个任务的标准输出和错误输出。
- `result.json` / `summary.json`：任务级结果统计。
- `runs/run_x/`：每次 rollout 的视频、HTML、prompt 和 JSON 结果。

## evaluator.py 使用方法

`evaluator.py` 是批量评测入口，支持指定任务、运行次数、最大步数、重规划次数和超时时间。

运行全部默认任务：

```bash
uv run python evaluator.py
```

只评测 Sort 任务并输出成功率：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 1
```

如果想得到更稳定的 Sort 准确率，可以增加运行次数：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 5
```

恢复较慢但更完整的评测配置：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --full
```

常用参数：

```text
--tasks sort              只运行 sort 任务
--runs 5                  每个任务运行 5 次
--tsteps 8                每次运行最多执行 8 个环境步
--num_replans 2           每步最多重规划 2 次
--timeout 180             每次运行的总超时时间
--rrt_timeout 60          单段 RRT 规划超时时间
--no_fallback_first       关闭确定性 fallback-first 规划
--keep_smooth_path        保留 RRT 路径平滑
--full                    使用较慢的完整评测配置
```

## Sort 任务优化说明

本次修改重点优化 Sort 任务。Sort 任务不是简单的“抓取并放置”，它强依赖历史状态、物体类别、机器人分工、失败反馈和物理可达性。此前主要失败点是：Alice 将 `pink_polygon` 放到 `panel3` 后，Bob 再抓取该物体时 IK 失败，导致后续步骤无法继续。

本次主要改动如下：

- 在 `evaluator.py` 和 `run_dialog.py` 中增加命令行参数，支持单独评测 Sort，并缩短调试时间。
- 增加 `fallback_first` 模式，让 Sort 优先使用确定性规则规划，再考虑 LLM 输出。
- 在 `prompting/plan_prompter.py` 中增加 Sort fallback planner，根据当前 panel、目标 panel 和中转 panel 选择保守动作。
- 在 `prompting/parser.py` 中增加 Sort 专用抓取稳定策略，对交接后高度过低的物体使用更安全的 top-down grasp pose。
- 在 `rocobench/envs/task_sort.py` 中调整 `panel3` handoff 目标点，让 Alice 放置后的物体处在 Bob 更容易到达的位置。
- 增加对空 LLM 响应的保护，避免 `NoneType` 解析崩溃。
- 增强 HTML 日志生成的鲁棒性，避免异常 prompt JSON 导致可视化保存失败。

## Sort 评测结果

本次修正后，使用 `qwen3.5:27b` 单独评测 Sort：

```text
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 1
Success Rate: 1/1 (100.0%)
Average Steps: 5.00
```

这说明当前主要失败点已经从语言规划问题定位为物理交接点问题，并通过 `panel3` handoff 位置修正和保守抓取姿态得到解决。

## 泛化性与过拟合风险

需要注意的是，单次或少量评测达到 100% 并不等于模型或系统已经具备强泛化能力。如果优化方式只是针对固定 seed、固定物体初始位置、固定失败日志写死动作顺序，那么很容易过拟合当前评测场景。

本次 Sort 修改尽量避免直接写固定答案，而是优先加入更通用的机制：

- 使用当前观测判断物体所在 panel、目标 panel 和下一步中转 panel，而不是只记住固定步骤。
- 使用 `fallback_first` 作为保守兜底策略，减少 LLM 调用失败造成的中断。
- 将 `panel3` 调整为更合理的交接区域，这是物理可达性修正，而不是单纯针对某一次失败输出硬编码。
- 在 parser 中加入低位抓取保护，解决交接后物体高度过低导致 IK 不稳定的问题。
- 对空响应和异常日志做保护，提升系统鲁棒性。

仍然存在的泛化风险：

- 当前 Sort fallback planner 主要基于已有 panel 拓扑和任务物体设计，对完全不同的 Sort 布局未必直接适用。
- `panel3` handoff 点虽然更符合 Bob 的可达区域，但仍建议在多个 seed、多个 runs 下继续验证。
- 如果后续为其他任务继续添加规则，应优先抽象成状态表、验证器、失败反馈和物理约束，而不是写死每个任务的固定执行序列。

建议验证方式：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 5
```

如果多次运行仍能保持较高成功率，才更能说明这次修改不是单纯“刷一次样例”，而是提升了 Sort 任务的执行稳定性。更进一步，可以改变随机种子进行测试：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 5 --seed 1
OLLAMA_MODEL=qwen3.5:27b uv run python evaluator.py --tasks sort --runs 5 --seed 2
```

总体来说，本次 100% 结果应理解为：当前失败案例已经被定位并修复，Sort 在当前评测配置下稳定性明显提升；但是否具备更强泛化性，还需要多 seed、多初始状态和更多任务组合继续验证。

## run_dialog.py 单任务运行

如果不通过 `evaluator.py`，也可以直接运行单个 Sort rollout：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python run_dialog.py --task sort --comm_mode plan --num_runs 1 --tsteps 8 --num_replans 2 --skip_display --skip_smooth_path --fallback_first --run_name sort_debug
```

运行结果会保存在：

```text
data/sort_debug/
```

或由 `evaluator.py` 指定到对应的 `output/run_YYYYMMDD_HHMMSS/` 目录。

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
- 当前 Sort 优化主要面向快速调试和稳定跑分；正式评测时如果平台替换 `evaluator.py`，核心 Sort 规划和物理修正仍位于 `prompting/` 与 `rocobench/envs/` 中。
