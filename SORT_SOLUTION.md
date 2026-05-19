# Sort 实训方案

本项目基于开源 RoCo / RoCoBench 框架完成 Sort 多机器人协同分拣任务。原框架使用大语言模型生成多机器人协作动作，通过文本解析器转换为机器人动作，再由 MuJoCo 环境、反馈模块和 RRT 路径规划器验证并执行。

## 任务理解

Sort 任务中，三个机器人需要将立方体分拣到指定目标面板：

- **机器人配置：**
  - Alice (UR5E + Robotiq)
  - Bob (Franka Panda)
  - Chad (UR5E + Suction)

- **目标分配：**
  - Alice: `blue_square` → `panel2`
  - Bob: `pink_polygon` → `panel4`
  - Chad: `yellow_trapezoid` → `panel6`

- **可达范围限制：**
  - Alice 只能到达 panel1, panel2, panel3
  - Bob 只能到达 panel3, panel4, panel5
  - Chad 只能到达 panel5, panel6, panel7

任务成功的关键是机器人之间的协作——当某个机器人的目标物体不在其可达范围内时，需要其他机器人帮助将物体移动到中间面板（panel3 或 panel5），然后由目标机器人完成最终放置。

## 基线方法

沿用 RoCoBench 的原始流程：

1. 环境通过 `describe_obs()` 给出物体位置、面板位置、机器人末端位姿和持物状态。
2. LLM 根据任务描述和动作格式输出每个机器人一条动作。
3. `LLMResponseParser` 解析 `PICK`、`PLACE`、`WAIT`。
4. `FeedbackManager` 检查动作约束、可达性、重复操作。
5. `PlannedPathPolicy` 使用 RRT / IK 在 MuJoCo 中规划和执行。

## 改进方向

### 1. Prompt 改进

在 `prompting/plan_prompter.py` 中增强协同提示：

- 明确每个机器人的目标立方体和目标面板。
- 明确每个机器人的可达面板范围。
- 允许 `WAIT` 动作，用于等待其他机器人完成协作。
- 鼓励机器人之间的帮助行为：如果目标物体不在可达范围内，请求其他机器人帮助移动。
- 优先使用 panel3 和 panel5 作为中间转接点。
- 如果反馈指出物体不可达或已在目标位置，则跳过该物体。

### 2. 三机器人协同机制

为 Sort 任务设计协作策略：

- 每个机器人优先处理自己的目标立方体。
- 如果目标立方体不在可达范围内：
  - Alice 的物体在右侧 → 请求 Bob 或 Chad 帮忙移动到 panel3
  - Chad 的物体在左侧 → 请求 Alice 或 Bob 帮忙移动到 panel5
  - Bob 的物体可以直接处理，或通过 panel3/panel5 中转
- 当一个机器人正在移动物体时，其他机器人可以 `WAIT` 或处理自己的任务。

### 3. 路径规划稳定性

新增路径和调试控制：

- `--rrt_timeout`：缩短失败规划等待时间。
- `--skip_smooth_path`：调试阶段跳过路径平滑。
- fallback 路径使用固定安全高度（抓取约 0.5，放置约 0.55）。
- 过滤已经到达目标位置的物体，避免生成无效动作。

### 4. 大模型适配

公共代码默认通过 `prompting/llm_client.py` 读取 OpenAI-compatible 环境变量；个人需要特殊客户端时，可以在本地创建被 `.gitignore` 忽略的 `prompting/openai_client.py`。

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=Qwen/Qwen3.5-27B
```

## 本轮 Sort 优化记录

本次修改重点优化 Sort 任务。Sort 任务不是简单的抓取并放置，它强依赖历史状态、物体类别、机器人分工、失败反馈和物理可达性。此前主要失败点是：Alice 将 `pink_polygon` 放到 `panel3` 后，Bob 再抓取该物体时 IK 失败，导致后续步骤无法继续。

主要公共改动如下：

- 在 `run_dialog.py` 中增加 `--rrt_timeout`、`--skip_smooth_path`、`--fallback_first`，支持更稳定的单任务调试。
- 在 `prompting/plan_prompter.py` 中增加 Sort fallback planner，根据当前 panel、目标 panel 和中转 panel 选择保守动作。
- 在 `prompting/parser.py` 中增加 Sort 专用抓取稳定策略，对交接后高度过低的物体使用更安全的 top-down grasp pose。
- 在 `rocobench/envs/task_sort.py` 中调整 `panel3` handoff 目标点，让 Alice 放置后的物体处在 Bob 更容易到达的位置。
- 增加对空 LLM 响应的保护，避免 `NoneType` 解析崩溃。
- 增强 HTML 日志生成的鲁棒性，避免异常 prompt JSON 导致可视化保存失败。

已观察到的验证结果：

```text
OLLAMA_MODEL=qwen3.5:27b uv run python run_dialog.py --task sort --comm_mode plan --num_runs 1 --tsteps 8 --num_replans 2 --skip_display --skip_smooth_path --fallback_first --run_name sort_debug
Run result: success in 5 steps
```

这说明当前主要失败点已经从语言规划问题定位为物理交接点问题，并通过 `panel3` handoff 位置修正和保守抓取姿态得到缓解。

### 泛化性与过拟合风险

单次或少量评测达到 100% 并不等于系统已经具备强泛化能力。如果优化方式只是针对固定 seed、固定物体初始位置、固定失败日志写死动作顺序，很容易过拟合当前评测场景。

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

建议继续验证：

```bash
OLLAMA_MODEL=qwen3.5:27b uv run python run_dialog.py --task sort --comm_mode plan --num_runs 5 --tsteps 8 --num_replans 2 --skip_display --skip_smooth_path --fallback_first --run_name sort_eval_seed0 --seed 0
OLLAMA_MODEL=qwen3.5:27b uv run python run_dialog.py --task sort --comm_mode plan --num_runs 5 --tsteps 8 --num_replans 2 --skip_display --skip_smooth_path --fallback_first --run_name sort_eval_seed1 --seed 1
OLLAMA_MODEL=qwen3.5:27b uv run python run_dialog.py --task sort --comm_mode plan --num_runs 5 --tsteps 8 --num_replans 2 --skip_display --skip_smooth_path --fallback_first --run_name sort_eval_seed2 --seed 2
```

## 推荐测试命令

快速调试前 3 步：

```bash
python run_dialog.py --task sort --comm_mode plan --num_runs 1 --tsteps 3 --num_replans 1 --skip_display --run_name sort_debug_3 --rrt_timeout 15 --skip_smooth_path
```

完整测试：

```bash
python run_dialog.py --task sort --comm_mode plan --num_runs 1 --tsteps 15 --num_replans 1 --skip_display --run_name sort_eval_15 --rrt_timeout 15 --skip_smooth_path
```

查看失败原因：

```bash
cat data/sort_eval_15/run_0/step_*/prompts/*feedback*.json
cat data/sort_eval_15/run_0/step_*/prompts/fallback_*.json
```

## 报告表述建议

可以这样描述本项目贡献：

> 本实训基于 RoCoBench 的 Sort 任务，沿用其 LLM 生成协作计划、环境反馈修正、RRT 路径规划和 MuJoCo 执行验证流程。针对三机器人协作中转、可达性约束和多阶段任务分配等问题，本文设计了基于中间面板的协作策略、明确的机器人能力边界提示、WAIT 协同动作和优先级任务调度机制，以提升多机器人协同分拣任务的成功率和效率。

## 代码实现关键点

### 核心代码文件

| 文件 | 功能 |
|------|------|
| `rocobench/envs/task_sort.py` | Sort任务环境定义 |
| `rocobench/envs/base_env.py` | 基础环境类和通用接口 |
| `rocobench/policy.py` | 策略执行和路径规划 |
| `rocobench/rrt.py` | RRT路径规划算法 |
| `real_world/prompts/feedback.py` | 反馈生成模块 |
| `real_world/prompts/parser.py` | LLM输出解析器 |

### 成功案例配置 (sort_test4)

```json
{
  "task": "sort",
  "tsteps": 8,
  "comm_mode": "plan",
  "output_mode": "action_only",
  "num_replans": 3,
  "llm_source": "gpt-4",
  "rrt_timeout": 20.0,
  "skip_smooth_path": true,
  "direct_waypoints": 5,
  "use_weld": 1
}
```

### 关键代码实现

#### 1. 任务环境初始化 (`task_sort.py`)

```python
class SortOneBlockTask(MujocoSimEnv):
    def __init__(self, filepath="rocobench/envs/task_sort.xml", ...):
        self.robot_names = ["ur5e_robotiq", "panda", "ur5e_suction"]
        self.robot_name_map = {
            "ur5e_robotiq": "Alice",
            "panda": "Bob",
            "ur5e_suction": "Chad",
        }
        # 定义3个立方体的目标面板
        self.cube_to_bin = dict(
            blue_square="panel2",
            pink_polygon="panel4",
            yellow_trapezoid="panel6",
        )
        # 定义每个机器人的可达面板范围
        self.reachable_panels = dict(
            Alice=["panel1", "panel2", "panel3"],
            Bob=["panel3", "panel4", "panel5"],
            Chad=["panel5", "panel6", "panel7"],
        )
        self.align_threshold = 0.1  # 放置精度阈值
```

**关键参数：**
- `align_threshold = 0.1` - 判断物体是否正确放置到面板的距离阈值
- `use_preplace = True` - 启用预放置机制
- 7个面板形成传送带结构：panel1 → panel7

#### 2. 任务上下文 (`SORT_TASK_CONTEXT`)

```python
SORT_TASK_CONTEXT = """
7 panels on the table, ordered left to right: panel1,...,panel7.
There are 3 cubes, each robot must place their cube on the correct target:
Alice: (blue_square, panel2)
Bob: (pink_polygon, panel4)
Chad: (yellow_trapezoid, panel6)

Each robot has limited reach range:
(Alice, [panel1, panel2, panel3])
(Bob, [panel3, panel4, panel5])
(Chad, [panel5, panel6, panel7])
"""
```

#### 3. 状态描述 (`describe_obs`)

```python
def describe_obs(self, obs: EnvState):
    # 描述每个立方体的位置和状态
    for cube_name in ONE_OBJ_EACH:
        object_desp += self.describe_cube_state(obs, cube_name) + "\n"
    # 描述每个机器人可达的立方体
    for robot_name, agent_name in self.robot_name_map.items():
        robot_desp += self.describe_robot_state(obs, robot_name) + "\n"
```

#### 4. 可达性检查 (`check_reach_range`)

```python
def check_reach_range(self, robot_name, point):
    reach_range = self.get_robot_reach_range(robot_name)
    # Alice: x=(-1.4, -0.1), Bob: x=(-0.7, 0.7), Chad: x=(0.2, 1.5)
    for i, axis in enumerate(["x", "y", "z"]):
        if point[i] < reach_range[axis][0] or point[i] > reach_range[axis][1]:
            return False
    return True
```

#### 5. 协同中转策略 (`describe_cube_state`)

```python
def describe_cube_state(self, obs, cube_name):
    # 检查立方体是否在目标面板上
    # 如果不在，描述当前位置和目标位置
    # 例如: "blue_square is on panel5 (target: panel2, needs to move)"
```

#### 6. 目标位置获取 (`get_target_pos`)

```python
def get_target_pos(self, agent_name, target_name):
    if 'panel' in target_name:
        # panel3 和 panel5 需要根据机器人类型调整偏移
        if target_name == 'panel3':
            if 'panda' in robot_name:
                ret[0] -= 0.12; ret[1] -= 0.1
            else:
                ret[0] += 0.12; ret[1] += 0.1
        # 返回面板位置，高度固定为 0.5
```

### 执行流程

1. **环境初始化** - 随机放置3个立方体在不同的面板上
2. **Prompt生成** - 描述立方体位置、目标面板、机器人可达范围
3. **LLM规划** - GPT-4生成协作策略
4. **反馈验证** - 检查动作合法性和可达性
5. **路径规划** - RRT算法规划无碰撞路径
6. **动作执行** - 在MuJoCo中执行PICK/PLACE/WAIT
7. **状态更新** - 更新立方体位置

### 成功执行示例 (sort_test4)

**Step 0 成功的关键：**
- 初始场景正确描述立方体位置（panel5, panel1, panel3）
- LLM理解蓝色方块需要通过Bob中转到panel2
- Alice可以在panel3拾取并移动到panel2

**协作策略示例：**
```
Round 1:
- Alice: PICK blue_square PLACE panel3 (蓝色方块不在Alice可达范围，先移动到panel3)
- Bob: WAIT
- Chad: PICK yellow_trapezoid PLACE panel6 (黄色梯形在Chad可达范围)

Round 2:
- Alice: WAIT
- Bob: PICK blue_square PLACE panel2 (Bob将蓝色方块从panel3移动到目标panel2)
- Chad: WAIT
```

## 引用

```bibtex
@misc{mandi2023roco,
      title={RoCo: Dialectic Multi-Robot Collaboration with Large Language Models},
      author={Zhao Mandi and Shreeya Jain and Shuran Song},
      year={2023},
      eprint={2307.04738},
      archivePrefix={arXiv},
      primaryClass={cs.RO}
}
```
