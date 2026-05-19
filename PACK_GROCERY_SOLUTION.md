# Pack Grocery 实训方案

本项目基于开源 RoCo / RoCoBench 框架完成 Pack Grocery 多机器人协同具身操作任务。原框架使用大语言模型生成多机器人协作动作，通过文本解析器转换为机器人动作，再由 MuJoCo 环境、反馈模块和 RRT 路径规划器验证并执行。

## 任务理解

Pack Grocery 任务中，Alice 是 UR5E + Robotiq 夹爪，Bob 是 Franka Panda 机械臂。两个机器人需要把桌面上的 6 个杂货物体放入箱子：

- `apple`
- `banana`
- `milk`
- `soda_can`
- `bread`
- `cereal`

成功的关键不是单个机器人抓取，而是两台机械臂在同一桌面和同一箱子附近移动时避免互撞、避免碰撞物体、避免生成不可达路径。

## 基线方法

沿用 RoCoBench 的原始流程：

1. 环境通过 `describe_obs()` 给出物体、箱子槽位、机器人末端位姿和持物状态。
2. LLM 根据任务描述和动作格式输出每个机器人一条动作。
3. `LLMResponseParser` 解析 `PICK`、`PLACE`、`PATH`。
4. `FeedbackManager` 检查动作约束、碰撞、可达性、路径平滑性。
5. `PlannedPathPolicy` 使用 RRT / IK 在 MuJoCo 中规划和执行。

## 改进方向

### 1. Prompt 改进

在 `prompting/plan_prompter.py` 中增强路径规划提示：

- 明确每轮每个机器人只能输出一个动作。
- 明确持物机器人必须先 `PLACE`，空手机器人不能 `PLACE`。
- 允许 `WAIT`，用来避免两个机械臂同时挤到箱子附近。
- 固定打包顺序：`cereal+milk`，`banana+bread`，`apple+soda_can`。
- Alice 优先处理 `cereal / banana / apple`，Bob 优先处理 `milk / bread / soda_can`。
- `PLACE` 使用高位路径，尤其是 `cereal` 和 `milk`，减少与箱子边缘和其他物体碰撞。
- 如果反馈指出物体不可达、碰到 world、姿态异常，则跳过该物体，继续处理其他未打包物体。

### 2. 多机器人协同机制

为 Pack Grocery 增加保守 fallback planner：

- 如果两个机器人都空手，优先按批次并行抓取左右分离的物体。
- 如果有机器人持物，只让一个机器人执行 `PLACE`，另一个机器人 `WAIT`。
- 优先让 Bob 放置手中物体，再让 Alice 放置，降低两只机械臂在箱口附近同时运动的概率。
- 如果某机器人没有可达物体，自动输出 `WAIT`，避免硬生成错误动作。

### 3. 路径规划稳定性

新增路径和调试控制：

- `--rrt_timeout`：缩短失败规划等待时间。
- `--skip_smooth_path`：调试阶段跳过路径平滑，减少单次实验时间。
- fallback 路径使用固定安全高度：
  - 抓取路径安全高度约 `0.62`
  - 放置路径安全高度约 `0.68`
  - 路径点高度限制在 `0.45` 到 `0.78`
- 过滤已经掉出工作区或目标位姿异常的物体，避免生成明显不可达路径。

### 4. 大模型适配

公共代码默认通过 `prompting/llm_client.py` 读取 OpenAI-compatible 环境变量；个人需要特殊客户端时，可以在本地创建被 `.gitignore` 忽略的 `prompting/openai_client.py`。

```bash
export OPENAI_BASE_URL=http://localhost:11434/v1
export OPENAI_API_KEY=ollama
export OPENAI_MODEL=Qwen/Qwen3.5-27B
```

后续如果要 finetune，可以收集 `data/<run_name>/run_*/step_*/prompts/*.json` 中的失败反馈和成功 fallback，构造监督微调样本：

- 输入：任务描述、场景描述、历史失败反馈。
- 输出：严格格式化的 `EXECUTE ... NAME ... ACTION ... PATH ...`。

## 推荐测试命令

快速调试前 3 步：

```bash
python run_dialog.py --task pack --comm_mode plan --num_runs 1 --tsteps 3 --num_replans 1 --skip_display --run_name pack_debug_3 --rrt_timeout 15 --skip_smooth_path --pack_fallback_first
```

完整 10 步测试：

```bash
python run_dialog.py --task pack --comm_mode plan --num_runs 1 --tsteps 10 --num_replans 1 --skip_display --run_name pack_eval_10 --rrt_timeout 15 --skip_smooth_path --pack_fallback_first
```

查看失败原因：

```bash
cat data/pack_eval_10/run_0/step_*/prompts/*feedback*.json
cat data/pack_eval_10/run_0/step_*/prompts/fallback_*.json
```

## 报告表述建议

可以这样描述本项目贡献：

> 本实训基于 RoCoBench 的 Pack Grocery 任务，沿用其 LLM 生成协作计划、环境反馈修正、RRT 路径规划和 MuJoCo 执行验证流程。针对本地小模型输出不稳定、双臂放置阶段碰撞、后期小物体不可达等问题，本文设计了 Pack 专用提示词、WAIT 协作动作、批次化任务分配、单臂放置策略、异常物体过滤和保守 fallback planner，以提升多机器人协同打包任务的成功率和调试效率。

## 代码实现关键点

### 核心代码文件

| 文件 | 功能 |
|------|------|
| `rocobench/envs/task_pack.py` | Pack任务环境定义 |
| `rocobench/envs/base_env.py` | 基础环境类和通用接口 |
| `rocobench/policy.py` | 策略执行和路径规划 |
| `rocobench/rrt.py` | RRT路径规划算法 |
| `real_world/prompts/feedback.py` | 反馈生成模块 |
| `real_world/prompts/parser.py` | LLM输出解析器 |

### 成功案例配置 (pack_test6)

```json
{
  "task": "pack",
  "tsteps": 15,
  "comm_mode": "plan",
  "output_mode": "action_and_path",
  "num_replans": 3,
  "llm_source": "gpt-4",
  "rrt_timeout": 20.0,
  "skip_smooth_path": true,
  "use_weld": 1
}
```

### 关键代码实现

#### 1. 任务环境初始化 (`task_pack.py`)

```python
class PackGroceryTask(MujocoSimEnv):
    def __init__(self, filepath="rocobench/envs/task_pack.xml", ...):
        self.robot_names = ["ur5e_robotiq", "panda"]
        self.robot_name_map = {
            "ur5e_robotiq": "Alice",
            "panda": "Bob",
        }
        # 定义6个杂货物品: apple, banana, milk, soda_can, bread, cereal
        self.item_names = PACK_ITEM_NAMES
        # 定义箱子6个槽位
        self.bin_slot_xposes = {
            "bin_front_left", "bin_front_right", "bin_front_middle",
            "bin_back_left", "bin_back_right", "bin_back_middle"
        }
```

**关键参数：**
- `align_threshold = 0.06` - 判断物体是否放入箱子的距离阈值
- `waypoint_std_threshold = 0.32` - 路径点标准差阈值
- `use_prepick = False`, `use_preplace = False` - 禁用预抓取和预放置

#### 2. 场景描述 (`describe_obs`)

```python
def describe_obs(self, obs: EnvState):
    # 描述桌子高度约束
    table_height = self.physics.data.body("table_top").xpos[2] + 0.15
    # 描述每个物品位置和状态（是否已在箱内）
    for name in self.item_names:
        full_desp += self.describe_object(obs, name) + "\n"
    # 描述箱子槽位坐标
    # 描述机器人末端位置和持物状态
```

#### 3. 反馈检查 (`get_task_feedback`)

```python
def get_task_feedback(self, llm_plan, pose_dict):
    # 检查PLACE到已占用槽位
    # 检查Bob的PICK可达性（x < -0.35 不可达）
    # 检查重复放置已打包物品
    # 检查槽位被占用情况
```

#### 4. 碰撞检测 (`get_allowed_collision_pairs`)

```python
def get_allowed_collision_pairs(self):
    # 允许物品与箱壁碰撞（打包后自然接触）
    # 允许物品之间碰撞（箱内物品自然接触）
    # 允许物品与桌子、世界碰撞
```

#### 5. 目标位置获取 (`get_target_pos`)

```python
def get_target_pos(self, agent_name, target_name):
    # 物品目标：返回物品_top的site位置
    # 槽位目标：返回槽位site位置
```

### 执行流程

1. **环境初始化** - 随机放置6个物品在桌面上
2. **Prompt生成** - 根据当前observation生成任务描述和动作选项
3. **LLM规划** - GPT-4生成每个机器人的PICK/PLACE/WAIT动作和路径
4. **反馈验证** - 检查动作合法性（可达性、碰撞、重复放置）
5. **路径规划** - RRT算法规划无碰撞路径
6. **动作执行** - 在MuJoCo中执行规划的动作
7. **状态更新** - 更新物体位置和机器人状态

### 成功执行示例 (pack_test6)

**Step 0 成功的关键：**
- 初始场景正确描述物品位置和机器人状态
- LLM生成合法的PICK动作和4点路径
- 路径点均匀分布，高度在0.45-0.78之间
- Bob处理右侧物品，Alice处理左侧物品

**Step 1+ 成功的关键：**
- Feedback正确识别已放置物品和空槽位
- 避免重复放置和碰撞
- WAIT动作有效协调双机械臂运动

## 公共规划器合并记录（PR #1）

- 动机：合并远程 PR #1 `Improve multi-arm path planning robustness`，提升多机械臂路径规划稳定性，同时保留 main 上 Cabinet release 规划中“已焊接物体视为 in-hand”的修复。
- 改动点：`rocobench/policy.py` 同时保留 `augment_release_plan_inhand` 和 `sparsify_validated_path`；`rocobench/rrt.py` 修正 near/center sampler 的区间采样；`rocobench/rrt_multi_arm.py` 使用末端局部坐标维护 in-hand 物体相对位姿、放宽 IK 容差、默认只允许末端执行器接触抓取物，并让 split plan 保留强制 waypoints。
- 运行命令：`python -m compileall run_dialog.py prompting rocobench/envs rocobench/policy.py rocobench/rrt.py rocobench/rrt_multi_arm.py`
- 验证结果：2026-05-19 语法检查通过；本次未重新跑完整仿真评测，建议按本任务推荐命令复验成功率。

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
