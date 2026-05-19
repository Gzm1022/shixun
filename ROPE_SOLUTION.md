# Rope 实训方案

本项目基于开源 RoCo / RoCoBench 框架完成 Rope 多机器人协同绳索操纵任务。原框架使用大语言模型生成多机器人协作动作，通过文本解析器转换为机器人动作，再由 MuJoCo 环境、反馈模块和 RRT 路径规划器验证并执行。

## 任务理解

Rope 任务中，两个机器人需要合作将一根长绳索放入狭窄的槽中：

- **机器人配置：**
  - Alice (UR5E + Robotiq)
  - Bob (Franka Panda)

- **任务目标：**
  - 将绳索的前端放入 `groove_left_end`
  - 将绳索的后端放入 `groove_right_end`

- **关键约束：**
  - 绳索很重，需要两个机器人同时抓取
  - 绳索和槽之间有障碍物墙，必须抬高绳索越过障碍物
  - 两个机器人的抓手距离必须保持固定，防止绳索掉落

任务成功的关键是两个机器人同步协作：同时抓取绳索两端，一起抬高越过障碍物，然后同时放入槽中。

## 基线方法

沿用 RoCoBench 的原始流程：

1. 环境通过 `describe_obs()` 给出绳索位置、槽位置、障碍物位置、机器人末端位姿和持物状态。
2. LLM 根据任务描述和动作格式输出每个机器人一条动作。
3. `LLMResponseParser` 解析 `PICK`、`PUT` 和路径坐标。
4. `FeedbackManager` 检查动作约束、碰撞、可达性。
5. `PlannedPathPolicy` 使用 RRT / IK 在 MuJoCo 中规划和执行。

## 改进方向

### 1. Prompt 改进

在 `prompting/plan_prompter.py` 中增强绳索操作提示：

- 明确两个机器人必须同时抓取绳索的两端。
- 必须抬高绳索越过障碍物（z >= 0.55）。
- 指定路径格式：必须包含四个均匀间隔的坐标点。
- Alice 负责绳索前端放入左侧槽，Bob 负责绳索后端放入右侧槽。
- 如果反馈指出 IK 失败或路径不可达，调整路径点。

### 2. 双臂协同机制

为 Rope 任务设计同步协作策略：

- **阶段一：抓取**
  - Alice 抓取 `rope_front_end`
  - Bob 抓取 `rope_back_end`
- **阶段二：抬升**
  - 两个机器人同时将绳索抬高到障碍物上方
- **阶段三：移动**
  - 两个机器人同步移动到槽的位置
- **阶段四：放置**
  - Alice 将前端放入 `groove_left_end`
  - Bob 将后端放入 `groove_right_end`
- **协调规则：**
  - 只有当两个机器人都抓住绳索时才能移动
  - 移动过程中保持抓手间距固定
  - 路径点必须均匀分布，确保同步

### 3. 路径规划稳定性

新增路径和调试控制：

- `--rrt_timeout`：缩短失败规划等待时间。
- `--skip_smooth_path`：调试阶段跳过路径平滑。
- 抬升高度必须超过障碍物顶部至少 0.08
- 路径点必须在机器人可达范围内
- 使用预定义的安全高度（抬升 z >= 0.55）

### 4. 大模型适配

公共代码默认通过 `prompting/llm_client.py` 读取 OpenAI-compatible 环境变量；个人需要特殊客户端时，可以在本地创建被 `.gitignore` 忽略的 `prompting/openai_client.py`。

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=Qwen/Qwen3.5-27B
```

## 推荐测试命令

快速调试前 3 步：

```bash
python run_dialog.py --task rope --comm_mode plan --num_runs 1 --tsteps 3 --num_replans 1 --skip_display --run_name rope_debug_3 --rrt_timeout 15 --skip_smooth_path
```

完整测试：

```bash
python run_dialog.py --task rope --comm_mode plan --num_runs 1 --tsteps 8 --num_replans 1 --skip_display --run_name rope_eval_8 --rrt_timeout 15 --skip_smooth_path
```

查看失败原因：

```bash
cat data/rope_eval_8/run_0/step_*/prompts/*feedback*.json
cat data/rope_eval_8/run_0/step_*/prompts/fallback_*.json
```

## 报告表述建议

可以这样描述本项目贡献：

> 本实训基于 RoCoBench 的 Rope 任务，沿用其 LLM 生成协作计划、环境反馈修正、RRT 路径规划和 MuJoCo 执行验证流程。针对绳索同步操作、障碍物规避和双臂协调等问题，本文设计了同步抓取-抬升-移动-放置的四阶段策略、统一高度约束、均匀路径点生成和位置交换策略，以提升双机器人协同绳索操纵任务的成功率和稳定性。

## 代码实现关键点

### 核心代码文件

| 文件 | 功能 |
|------|------|
| `rocobench/envs/task_rope.py` | Rope任务环境定义 |
| `rocobench/envs/base_env.py` | 基础环境类和通用接口 |
| `rocobench/policy.py` | 策略执行和路径规划 |
| `rocobench/rrt.py` | RRT路径规划算法 |
| `real_world/prompts/feedback.py` | 反馈生成模块 |
| `real_world/prompts/parser.py` | LLM输出解析器 |

### 成功案例配置 (rope_test5)

```json
{
  "task": "rope",
  "tsteps": 5,
  "comm_mode": "plan",
  "output_mode": "action_and_path",
  "num_replans": 3,
  "llm_source": "gpt-4",
  "rrt_timeout": 20.0,
  "skip_smooth_path": true,
  "direct_waypoints": 5,
  "split_parsed_plans": true,
  "use_weld": 1
}
```

### 关键代码实现

#### 1. 任务环境初始化 (`task_rope.py`)

```python
class MoveRopeTask(MujocoSimEnv):
    def __init__(self, filepath="rocobench/envs/task_rope.xml", ...):
        self.robot_names = ["ur5e_robotiq", "panda"]
        self.robot_name_map = {
            "ur5e_robotiq": "Alice",
            "panda": "Bob",
        }
        # 定义绳索的前后端
        ROPE_FRONT_BODY = "CB0"
        ROPE_BACK_BODY = "CB24"
        # 定义槽的位置
        self.groove_pos = dict(
            groove_left_end=(x, y, z),
            groove_right_end=(x, y, z)
        )
        self.align_threshold = 0.2  # 放置精度阈值
        self.waypoint_std_threshold = 0.3  # 路径点标准差阈值
```

**关键参数：**
- `align_threshold = 0.2` - 判断绳索是否放入槽的距离阈值
- `waypoint_std_threshold = 0.3` - 路径点标准差阈值
- 障碍物顶部高度 + 0.08 = 最小抬升高度

#### 2. 动作空间定义

```python
ROPE_ACTION_SPACE = """
[Action Options]
1) PICK <obj> PATH <path>: only PICK if your gripper is empty
2) PUT <obj> <location> PATH <path>: PUT on groove only if holding rope
"""
```

#### 3. 状态描述 (`describe_obs`)

```python
def describe_obs(self, obs: EnvState):
    # 描述桌子高度约束
    table_height = self.physics.data.body("table_top").xpos[2] + 0.15
    # 描述障碍物顶部高度
    obstacle_top_z = max([physics.data.site(n).xpos[2] for n in OBSTACLE_CORNER_NAMES])
    # 描述槽位置
    # 描述绳索两端位置
    # 描述机器人位置和持物状态
    # 当两个机器人都抓住绳索时，生成PUT路径示例
```

#### 4. 完成条件 (`get_reward_done`)

```python
def get_reward_done(self, obs):
    # 绳索前端和后端都在槽内
    dist_lf = np.linalg.norm(groove_left - rope_front)
    dist_rb = np.linalg.norm(groove_right - rope_back)
    # 或交叉放置也可接受
    dist_lb = np.linalg.norm(groove_left - rope_back)
    dist_rf = np.linalg.norm(groove_right - rope_front)
    done = (dist_lf < 0.2 and dist_rb < 0.2) or \
           (dist_lb < 0.2 and dist_rf < 0.2)
    done = done and 'groove_bottom' in obs.objects['rope'].contacts
```

#### 5. 反馈检查 (`get_task_feedback`)

```python
def get_task_feedback(self, llm_plan, pose_dict):
    # 检查PUT动作是否在持有绳索时才能执行
    for agent_name, action_str in llm_plan.action_strs.items():
        if 'PUT' in action_str and not holding[agent_name]:
            feedback += f"{agent_name} cannot PUT: gripper is empty"
```

### 执行流程

1. **环境初始化** - 随机放置绳索和障碍物
2. **Prompt生成** - 描述绳索位置、槽位置、障碍物高度、机器人状态
3. **LLM规划** - GPT-4生成PICK/PUT动作和路径
4. **反馈验证** - 检查持有状态和动作合法性
5. **路径规划** - RRT算法规划无碰撞路径
6. **动作执行** - 在MuJoCo中执行PICK/PUT
7. **状态更新** - 更新绳索位置

### 成功执行示例 (rope_test5)

**Step 0 成功的关键：**
- 初始场景正确描述绳索两端位置和机器人可达范围
- LLM生成合法的PICK动作（Alice抓前端，Bob抓后端）
- 路径点均匀分布，高度在安全范围内

**四阶段策略：**
```
阶段一（抓取）:
- Alice: PICK rope_front_end PATH [p1, p2, p3, p4]
- Bob: PICK rope_back_end PATH [p1, p2, p3, p4]

阶段二（抬升）:
- Alice: WAIT PATH [保持高度]
- Bob: WAIT PATH [保持高度]

阶段三（移动）:
- Alice和Bob同步移动到槽上方

阶段四（放置）:
- Alice: PUT rope_front_end groove_left_end PATH [p1, p2, p3, p4]
- Bob: PUT rope_back_end groove_right_end PATH [p1, p2, p3, p4]
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