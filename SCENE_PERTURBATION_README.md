# RoCoBench 场景扰动泛化测试 README

本文档记录本次围绕 Sort、Rope、Sweep 三个任务新增的“参数化场景扰动生成器”。该机制的目标不是只提升固定 benchmark seed 上的分数，而是构造一组可复现、可分难度、可批量评测的未见场景，用来检验多智能体 LLM 规划器是否真正具备泛化能力。

## 1. 创新点概述

原始 RoCoBench 的任务场景相对固定。模型或规则 fallback 在固定布局下可能表现很好，但这不一定说明它理解了任务结构，也可能只是学会了固定模板、固定目标和固定动作顺序。

本次创新点是：

> 构建面向 RoCoBench 的参数化场景扩展机制，通过对物体数量范围内的空间布局、目标位置、障碍物位置和任务约束进行扰动，形成一组可控难度的泛化测试场景，用于评估多智能体 LLM 规划器在未见场景下的鲁棒性。

当前已实现三个任务：

- Sort：扰动物体初始 panel、panel 内偏移、目标 panel 映射。
- Rope：扰动绳子初始姿态、groove 目标位置、障碍墙位置/角度、抓取点可达性。
- Sweep：扰动垃圾块分布、垃圾密度和 trash bin 目标位置。

所有扰动默认关闭，原始行为保持不变。只有显式传入 `*_variant` 参数时才启用泛化测试。

## 2. 通用评测入口

新增本地评测脚本：

```bash
local_task_evaluator.py
```

该脚本会批量调用 `run_dialog.py`，然后读取每个 run 目录中的：

```text
steps*_success_*.json
```

并汇总：

- `successes`：成功次数；
- `total`：总运行次数；
- `success_rate`：成功率；
- `timed_out`：超时次数；
- `avg_elapsed_time`：平均耗时；
- `details`：每个 run 的 step、success、timeout 和 elapsed_time。

输出文件位于：

```text
data/<run_name>/local_eval_summary.json
```

查看所有评测结果：

```bash
find data -name "local_eval_summary.json" -print -exec cat {} \;
```

## 3. Sort 扰动机制

### 3.1 参数

Sort 新增参数：

```bash
--sort_variant default|easy|medium|hard
--sort_layout_noise <float>
--sort_target_mode fixed|permuted
```

默认：

```bash
--sort_variant default --sort_target_mode fixed
```

此时保持原始 RoCoBench Sort 行为。

### 3.2 扰动内容

Sort 任务中三个物体仍使用原 XML 中的：

```text
blue_square
pink_polygon
yellow_trapezoid
```

扰动包括：

- 初始 panel 改变；
- panel 内 xy 偏移；
- 物体初始旋转角度；
- 可选目标映射打乱。

`medium` 难度下，物体会被放在非目标 panel 上，并加入中等 xy 偏移。

`hard + permuted` 难度下，目标映射也会打乱，例如：

```text
blue_square -> panel6
pink_polygon -> panel2
yellow_trapezoid -> panel4
```

这样模型不能继续套用固定模板：

```text
blue_square -> panel2
pink_polygon -> panel4
yellow_trapezoid -> panel6
```

### 3.3 关键代码

主要改动：

```text
rocobench/envs/task_sort.py
prompting/plan_prompter.py
run_dialog.py
local_task_evaluator.py
```

环境侧新增当前目标映射 `cube_to_bin` 的动态配置。prompt 和 fallback planner 都读取当前环境中的 `cube_to_bin`，避免写死颜色到目标 panel 的关系。

### 3.4 推荐命令

Baseline：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks sort --runs 5 --tsteps 8 --scene_seed 42 --variant default
```

Medium：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks sort --runs 5 --tsteps 8 --scene_seed 42 --variant medium
```

Hard：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks sort --runs 5 --tsteps 10 --scene_seed 42 --variant hard --sort_target_mode permuted
```

### 3.5 已观察现象

当前已得到一组 Sort baseline 结果：

```text
Sort default: 5/5 = 100%
Timeout: 0/5
Average elapsed time: about 66.1s
Steps: mostly 5-6
```

说明原始 Sort 场景下，当前 fallback、parser 抓取高度修正和 panel3/panel5 中转策略较稳定。

后续重点观察：

- medium 是否仍能保持高成功率；
- hard + permuted 是否暴露固定目标模板依赖；
- 失败时是否来自错误目标映射、错误中转 panel，还是物理 IK/RRT 问题。

## 4. Rope 扰动机制

### 4.1 参数

Rope 新增参数：

```bash
--rope_variant default|easy|medium|hard
--rope_goal_noise <float>
--rope_obstacle_noise <float>
--rope_pose_noise <float>
```

默认：

```bash
--rope_variant default
```

此时保持原始 Rope 随机场景行为。

### 4.2 扰动内容

Rope 是强物理约束任务。扰动内容包括：

- 绳子初始位置；
- 绳子绕 z 轴初始角度；
- 绳子外力扰动强度；
- 障碍墙位置；
- 障碍墙角度；
- groove 目标位置；
- rope endpoint 抓取点 inward offset；
- 抓取目标高度范围。

`medium` 会扩大绳子姿态、障碍墙和目标槽的扰动范围。

`hard` 会进一步扩大扰动，并允许额外 noise：

```bash
--rope_goal_noise 0.03
--rope_obstacle_noise 0.03
--rope_pose_noise 0.03
```

### 4.3 关键代码

主要改动：

```text
rocobench/envs/task_rope.py
run_dialog.py
local_task_evaluator.py
ROPE_SOLUTION.md
```

Rope 场景描述会提示当前为 perturbed scene，并输出当前：

```text
rope_front_end
rope_back_end
groove_left_end
groove_right_end
obstacle_wall_front_top
obstacle_wall_back_top
```

这要求 planner 根据当前坐标规划，而不是复用固定路径。

### 4.4 推荐命令

Baseline：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks rope --runs 5 --tsteps 10 --scene_seed 42 --variant default
```

Medium：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks rope --runs 5 --tsteps 10 --scene_seed 42 --variant medium
```

Hard：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks rope --runs 5 --tsteps 12 --scene_seed 42 --variant hard --rope_goal_noise 0.03 --rope_obstacle_noise 0.03 --rope_pose_noise 0.03
```

### 4.5 已观察现象

当前已得到一组 Rope medium 结果：

```text
Rope medium: 3/5 = 60%
Timeout: 2/5
Average elapsed time: about 343.0s
Successful runs: around 53-55s
Failed runs: timeout at step 3
```

这个现象说明 Rope 的主要问题不是语义规划完全失败，而是扰动后物理可执行性显著下降。成功样例很快完成，失败样例主要卡在 RRT/IK/碰撞约束上。

可能原因：

- 绳子端点位置导致抓取 IK 更难；
- 障碍墙挡住低空路径；
- Panda/Bob 在某些 x/y 区域高位路径 IK 不稳定；
- 两臂同步带绳移动时，路径约束更紧；
- fallback 候选路径没有足够快地绕开不可行通道。

后续优化方向：

- 根据障碍墙位置动态调整 `lane_y`；
- 根据 obstacle top 动态调整 lift height；
- 对 Bob 增加更多右侧安全通道候选；
- 增加 timeout 前的快速失败判定；
- 对失败 run 的 step 3 单独复现并分析 RRT failure reason。

## 5. Sweep 扰动机制

### 5.1 参数

Sweep 新增参数：

```bash
--sweep_variant default|easy|medium|hard
--sweep_cube_noise <float>
--sweep_target_noise <float>
```

默认：

```bash
--sweep_variant default
```

此时保持原始 RoCoBench Sweep 行为。

### 5.2 扰动内容

Sweep 扰动包括：

- cube 初始 xy 分布范围；
- cube 间距；
- 垃圾密度；
- hard 模式下的 clustered 垃圾分布；
- trash bin 目标位置扰动。

`medium` 生成更宽的垃圾分布，并对 trash bin 位置做中等扰动。

`hard` 生成更密集的垃圾分布，测试 Bob 扫动路径和 Alice dustpan 对位能力。

### 5.3 关键代码

主要改动：

```text
rocobench/envs/task_sweep.py
run_dialog.py
local_task_evaluator.py
SWEEP_SOLUTION.md
```

场景描述会输出当前：

```text
trash_bin target top
red_cube
green_cube
blue_cube
```

并提示当前为 perturbed Sweep scene。

### 5.4 推荐命令

Baseline：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks sweep --runs 5 --tsteps 10 --scene_seed 42 --variant default
```

Medium：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks sweep --runs 5 --tsteps 10 --scene_seed 42 --variant medium
```

Hard：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python local_task_evaluator.py --tasks sweep --runs 5 --tsteps 12 --scene_seed 42 --variant hard --sweep_cube_noise 0.03 --sweep_target_noise 0.03
```

### 5.5 预期观察点

Sweep 的重点不是目标映射，而是同步协作和物理接触：

- Alice 是否能一直等待在同一个 cube 的 dustpan 位置；
- Bob 是否只在 Alice ready 后 sweep；
- sweep 后 Alice 是否及时 dump；
- 垃圾块密集时是否发生重复扫、漏扫或 cube 间干扰；
- trash bin 位置变化后 dump 是否仍可靠。

若 hard 成功率下降，通常说明：

- MOVE 阶段对位不够精确；
- SWEEP 阶段推扫方向或距离不足；
- 密集 cube 造成接触干扰；
- DUMP 对 trash bin 位置扰动不够鲁棒。

后续优化方向：

- 根据 cube 位置和 trash bin 方向动态选择 sweep 方向；
- 对 clustered cube 增加“先扫边缘目标”的排序；
- 增加 dustpan ready 距离和朝向检查；
- 让 fallback 根据 cube 到 dustpan 的几何关系选择更安全目标。

## 6. 指标汇总模板

实验完成后可以按如下表格总结：

| Task | Variant | Runs | Success | Success Rate | Timeout | Avg Time | Main Failure |
|---|---:|---:|---:|---:|---:|---:|---|
| Sort | default | 5 | 5 | 100% | 0 | 66.1s | none |
| Sort | medium | 5 | TBD | TBD | TBD | TBD | TBD |
| Sort | hard | 5 | TBD | TBD | TBD | TBD | TBD |
| Rope | default | 5 | TBD | TBD | TBD | TBD | TBD |
| Rope | medium | 5 | 3 | 60% | 2 | 343.0s | RRT/IK timeout |
| Rope | hard | 5 | TBD | TBD | TBD | TBD | TBD |
| Sweep | default | 5 | TBD | TBD | TBD | TBD | TBD |
| Sweep | medium | 5 | TBD | TBD | TBD | TBD | TBD |
| Sweep | hard | 5 | TBD | TBD | TBD | TBD | TBD |

## 7. 报告表述建议

可以在报告中这样概括：

> 本项目不仅针对固定 RoCoBench 场景进行任务优化，还进一步构建了参数化场景扰动生成器。对于 Sort、Rope、Sweep 三类代表性任务，分别从符号目标映射、连续绳体物理约束和清扫接触分布三个角度设计了 easy/medium/hard 三档未见场景。通过统一的本地评测脚本统计成功率、超时次数和平均耗时，可以更系统地分析 LLM 多机器人规划器在固定模板之外的泛化能力和失败模式。

这部分创新的价值在于：

- 从“单一成功率”扩展到“难度分层成功率”；
- 从“固定 seed 调参”扩展到“可复现泛化测试”；
- 能区分语义规划失败和物理执行失败；
- 为后续针对性优化 fallback、parser 和 RRT 候选路径提供依据。
