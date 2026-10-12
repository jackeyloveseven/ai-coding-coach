# exptool —— 训练实验的统一入口

`exp` 把「启动、查看、续跑实验」这套动作收在一个命令里。它本身没什么魔法，核心是两条：

1. **每条命令执行前都打印它背后真正跑的那条命令**（灰色的 `+ ssh ...`）。复制下来自己改着用，熟了以后不用这个工具也能干。
2. **读数看趋势，不看单步**。把整段训练切成若干段比较均值，因为单步值跳动大、没有信息量。

这个目录是 [ai-coding-coach](../) skill 的配套工具。skill 里 `references/training-run-literacy.md` 讲的是判断方法，这里是那套方法的执行入口。

> **这是脱敏的通用版。** 主机名、共享盘路径、奖励服务地址全部走配置文件，仓库里只有占位符。你按自己的环境填。

---

## 快速开始（本地就能跑，不需要集群）

```bash
cd exptool
cp runs.conf.example runs.conf
./exp list              # 应该看到 demo-sft
./exp status demo-sft   # 看示例实验的进度
```

> 用 zip 下载的话记得先 `chmod +x exp`；`git clone` 不需要，可执行位是带着的。

`runs.conf.example` 里的机器列写的是 `local`，表示就在本机跑、不走 ssh。`examples/demo-sft/` 是一个假的实验目录，用来让你先看清输出长什么样。

接你自己的集群：

```bash
mkdir -p ~/.config/exptool
cp exptool.conf.example ~/.config/exptool/config
cp runs.conf.example ~/.config/exptool/runs.conf
# 改这两个文件，填你自己的机器和实验
./exp list
```

`exp` 本身可以直接放在 `~/bin` 下：

```bash
ln -s "$PWD/exp" ~/bin/exp
```

---

## 命令

| 命令 | 干什么 |
|---|---|
| `exp list` | 登记了哪些实验，哪些还在跑 |
| `exp status [名字]` | 进度、指标趋势、健康检查（默认看登记表第一行那个） |
| `exp log [名字]` | 实时滚动看日志（Ctrl+C 退出，训练不会停） |
| `exp errors [名字]` | 搜报错 |
| `exp gpu <机器>` | 看某台机器的卡空不空 |
| `exp start <名字>` | 启动（先给你看 GPU，确认后才起） |
| `exp stop <名字>` | 停止 |
| `exp attach [名字]` | 进 tmux 画面（退出按 Ctrl+B 再按 D） |
| `exp config [名字]` | 打印这个实验的 `launch.sh` |

---

## 登记实验：`runs.conf`

一行一个实验，六列，空格或 Tab 分隔。`#` 开头的行和空行忽略。

```
名字             机器    目录                   方法      tmux   说明
demo-sft         local   ./examples/demo-sft    sft       -      示例
hps-185          node-5  /shared/runs/awm_long  awm-hps   awm-1  400 步长跑
```

| 列 | 说明 |
|---|---|
| 名字 | 随便取，不和别人重复就行。`exp status` / `log` / `start` 都用它 |
| 机器 | `ssh` 得通的主机名；写 `local` 表示就在本机跑 |
| 目录 | **要写到具体那一次运行**。同一个 SFT 下面同时有 `smoke/` 和 `formal/`，就写 `formal/`，否则两次运行的记录会混在一起 |
| 方法 | 决定用哪个脚本看进度，见下节 |
| tmux | 写 `-` 表示不归 `exp start/stop` 管（别人起的、或已经结束了） |
| 说明 | 随便写，最后一个字段，可以带空格 |

---

## 进度读取器

**方法**列写 `awm-hps`，`exp` 会去找 `progress/awm.py`——只看 `-` 前面那段，后面随你写，用来区分奖励模型之类。找不到同名脚本就用 `progress/generic.py`。

所以 `sft`、`dpo`、`diffusionnft` 不写任何代码也能直接看。

### `generic.py`

按这个顺序找指标，用找到的第一种：

| 来源 | 谁会写 |
|---|---|
| `*.jsonl`（每行一个 JSON） | 自己写的训练代码、webtrainer、AWM |
| `trainer_state.json` | HuggingFace Trainer，TRL 的 SFT、DPO 都会写 |
| `events.out.tfevents.*` | tensorboard；要求远端装了 tensorboard |
| 日志里的 `loss=0.12`、`reward: 0.5` 这类文字 | 几乎所有训练脚本 |

```bash
python3 progress/generic.py <运行目录>
python3 progress/generic.py <运行目录> --segments 10   # 改段数（默认 8）
python3 progress/generic.py <运行目录> --limit 8       # 多看几个指标（默认 6）
python3 progress/generic.py <运行目录> --all           # 连 step/epoch 也一起显示
```

输出长这样：

```
来源: metrics.jsonl ｜ 共 240 个点 ｜ 切 8 段
指标                       1         2         3         4         5         6         7         8       变化
grad_norm               1.47      1.14     0.904     0.736     0.599     0.502     0.444     0.402      -1.07
loss                    2.27      1.42     0.958     0.661     0.506     0.404     0.368     0.325      -1.95
lr                  1.88e-05  1.65e-05  1.42e-05  1.19e-05  9.58e-06  7.27e-06  4.96e-06  2.65e-06  -1.62e-05
rewards/accuracies     0.584     0.716     0.795     0.854     0.886     0.906      0.92      0.93      0.346
```

名字里带 `loss`、`reward`、`acc`、`margin`、`grad`、`kl`、`lr` 的优先显示。`step`、`epoch` 这类元数据默认不占显示位（`--all` 可以放出来）。

### 写一个专用读取器

当这个方法的收益不能靠训练 loss 看出来时，就需要一个专用的。典型是 RL 那类——训练奖励每步换题，跳动很大，盯着看没有信息量，真正说明问题的是**固定评测集**上的分数。

复制 `progress/example.py`，改名成 `progress/<你的方法>.py`，把读文件那段改成你的格式。文件头的注释写了约定。

---

## 健康检查

`exp status` 会看这几项：

- **tmux 还在不在**。不在了就 `exp errors` 看报错。
- **标记文件**（默认找 `FAILED` 和 `DONE`，可在配置里改）。
- **日志最后更新**。超过 30 分钟没动，可能卡在奖励服务、NCCL 或死锁上。
- **奖励服务**（配了 `REWARD_HEALTH_URL` 才查）。返回 `200` 或 `401` 都算活着（`401` 只是没带凭证），`000` 是没响应。

---

## 哪些验证过，哪些没有

这个工具是照着一份使用手册重写的（原实现不在手边），所以要说清楚边界：

**在本地跑过、有测试覆盖的：**

- `progress/generic.py` 的全部逻辑——来源优先级、坏数据跳过、日志文字解析、分段、指标筛选。46 项断言，`python3 tests/test_generic.py`
- `exp list / status / config / errors / help` 在 `local` 模式下的完整链路，以及各种错误路径（不认识的命令、不认识的实验、登记表不存在）。17 项断言，`bash tests/test_exp.sh`

**没有验证过的（没有集群可测）：**

- 走 ssh 的那条路（`run_on` 的远端分支）——逻辑和本地分支对称，但没实跑过
- `exp start / stop / attach`——依赖 tmux，只在 `local` 模式之外用到
- `exp gpu` 的 `nvidia-smi` 输出解析——按标准 csv 格式写的，没在真卡上试过
- tensorboard 事件文件读取——需要装了 `tensorboard` 才能走到，本地没测
- 奖励服务的 curl 探测

这些地方如果不对，改起来都是几行的事，但请先拿一台机器试一下再用。

---

## 跑测试

```bash
python3 tests/test_generic.py    # 进度读取器
bash    tests/test_exp.sh        # exp 命令本身（只用 local 模式）
```

Windows 上 `python3` 常常是 Microsoft Store 的占位程序（跑起来直接退出），直接用 `py` 代替即可：

```bash
py -X utf8 tests/test_generic.py
bash    tests/test_exp.sh        # 这个会自己探测解释器，不用管
```
