# ai-coding-coach

[![tests](https://github.com/jackeyloveseven/ai-coding-coach/actions/workflows/test.yml/badge.svg)](https://github.com/jackeyloveseven/ai-coding-coach/actions/workflows/test.yml)

> **一边帮你写代码，一边把你教成能一眼看出 AI 哪里写错了的算法工程师。**

面向初级 / 中级算法工程师。不追求写得比 AI 快，追求**审得动** AI。

介绍页：<https://jackeyloveseven.github.io/ai-coding-coach/>

```
/plugin install ai-coding-coach --marketplace jackeyloveseven/ai-coding-coach
```

<sub>其他装法见[安装](#安装)。</sub>

---

## 它长什么样

**🟡 黄档** —— 你贴一段评估代码给我看。我改完之后，附一个「读懂检查点」：

> - **关键行**：`model.eval()` 和 `torch.no_grad()` 缺一不可。少了 `eval()`，dropout 和 BatchNorm 还留在训练态，指标会又抖又偏低——而且**不报错**。
> - **静默风险**：`total += batch_loss` 没乘 batch size，最后除以 `len(loader)` 得到的是「每 batch 平均」。最后一批样本不满时它会偏。验证：跟 `总loss / 总样本数` 对一下。
> - **先预测**：这段跑完，`val_loss` 和训练最后几个 step 的 `train_loss` 差多少？
> - **自测**：把 `model.eval()` 删掉，指标会变好还是变差？为什么？

**🔴 红档** —— 你要自己实现 DPO loss。我不给答案，给脚手架：

> 你写一版，我们再对照：
>
> ```python
> def dpo_loss(policy_logps, ref_logps, chosen, rejected, beta=0.1):
>     """返回 (loss, chosen_rewards, rejected_rewards)。
>     写完和官方实现比 torch.allclose。"""
> ```
>
> 一个提示：`beta` 在这份实现里应该出现**两次**，想清楚分别为什么。

想直接要答案？回一句「**直接给**」，立刻给，不追问。

---

## 为什么做这个：四个失败模式

写代码在快速贬值，「判断」没有。下面四条是初级算法工程师在 AI 时代最常摔的坑——这个仓库里的每一样东西，都对着其中一条。

### #1 能跑通，但结果悄悄是错的

**问题**：算法工程里最贵的 bug 不是报错，是**能跑、指标也出来了、但其实错了**。训练集和验证集的顺序反了、指标算在了增强后的数据上、loss 累加时样本数没除对——这些都不崩，只会让你在错误的结论上再走三个月。

**解法**：黄档的**读懂检查点**专门盯这个。改完代码附一段：关键行为什么这么写、**这段最可能悄悄错在哪**、你能直接跑的验证方式。清单见 [`references/practice-menu.md`](references/practice-menu.md)。

### #2 loss 降了，但不知道那是不是真的学到东西

**问题**：loss 一路降、指标涨了 3 个点——是改动有效，还是数据泄露、随机波动、reward hacking？**结果出来之后再决定「涨多少算有效」，几乎总会得出「有效」的结论。**

**解法**：**事前记录**（假设 / 对照 / 变量 / **判据** / 止损 / 预测）跑之前写完；`exp status` 再把**判据**印在指标正上方。读数那一刻，你被迫对照事前定下的标准。见 [`references/experiment-design.md`](references/experiment-design.md)。

### #3 实验跑完了，下一步全靠感觉

**问题**：继续还是停、换哪个参数、要不要加卡——这些决定没人替你做。AI 也不知道你的业务和数据，给不出可靠建议。

**解法**：红档不给答案，给脚手架，请你先说出「我打算下一步做什么、为什么」，再对照。决定权在你。

### #4 我越来越不做「判断」这个动作了

**问题**：代码几乎都由 agent 写，你审得越来越少。判断力不是被 AI 拿走的，是你不再练习而退化的——它不会因为 AI 变强而消失，反而因为 AI 产出变多而更值钱。

**解法**：掌握度台账按间隔复习（1 / 3 / 7 / 16 / 35 天）提醒到期主题，稳了的降一档、反复出错的升一档。想主动练就敲 `/coach-drill`。

---

> 贯穿全篇的一条判断：**分工的边界不在「谁写代码」，而在「谁对结果负责」。**

---

## 两个 skill 怎么分工

这个仓库装两个 skill，按**谁能触发**分工：

| skill | 触发方式 | 干什么 | 常驻成本 |
|---|---|---|---|
| `ai-coding-coach` | **自动**（model-invoked） | 常驻纪律。你写代码、调 bug、看日志时自动生效，顺手把你拉进判断 | ~240 token |
| `/coach-drill` | **只有你手打**（user-invoked） | 显式编排。想主动练 15–25 分钟时敲它，从台账挑到期的主题带你练 | ~70 token |

两个加起来，每次会话只多占 **约 310 token**（`claude plugin details` 自己算的），真正的内容（3.5k / 1.1k）只在你用到时才加载。所以常驻**不构成上下文负担**——一条 CLAUDE.md 规则、一个 MCP server 的描述，往往比这还贵。

那 70 token 是 `coach-drill` 的 description：`disable-model-invocation` 只关掉了**自动触发**，描述仍然留在技能列表里，好让你知道有这扇门。

---

## 它怎么工作

### 1. 每次任务先分档

用两个问题决定该教多少：**出错时后果有多隐蔽？** 亲手做一遍对判断力的价值有多大？

| 档 | 典型任务 | 教练的做法 |
|---|---|---|
| 🟢 **绿：放手** | 样板代码、argparse、日志、画图、shell 命令 | 直接做好，**不加教学**（学了不增值，说教只会烦人） |
| 🟡 **黄：读懂** | 数据处理、训练循环、loss 实现、评估代码、超参改动 | 做完，附一个 6 行以内的「读懂检查点」 |
| 🔴 **红：亲手** | attention / loss / 采样 / 优化器、方案设计、**实验设计**、**读数、决定下一步** | 进入教练模式：先请你出手，再给反馈 |

拿不准时按黄档处理。宁可少教，也不在该打断的地方打断。

### 2. 黄档：读懂检查点

不是泛泛地说「你要理解这段代码」，而是具体到：

- **关键行**：1–3 处最重要的代码，说明为什么这样写
- **静默风险**：这段最可能悄悄出错的一两点 + 你能直接跑的验证方式
- **运行前先预测**：shape / loss 量级 / 输出形态
- **自测**：一道带情境的题，不附答案

其中「静默风险」是核心——算法工程里最危险的 bug 是**能跑、指标也出来了、但其实错了**。

### 3. 红档：教练模式

先给脚手架（函数签名、期望输出、和官方实现比 `allclose` 的验证手段），请你先写一版，再对比差异。

**教学是附加，不是关卡。** 想直接要答案，回一句「直接给」，立刻给，不追问。

### 4. 掌握度台账（可选）

经你同意后，用 `scripts/ledger.py` 在本地记录每个主题的掌握等级，按间隔复习（1 / 3 / 7 / 16 / 35 天）提醒到期主题，并据此自动调档：**稳了的降一档，反复出错的升一档。**

没有本地存储时（比如网页版对话），改用「学习卡」——粘贴式的纯文本，你自己存进笔记，下次对话开头贴回来。

> 只记主题标签、结果、一句话备注。不记代码、主机名、内网地址、密钥、同事姓名。

### 5. 强度可调

| 强度 | 触发 | 效果 |
|---|---|---|
| 轻量 | 「赶时间」「直接做」 | 三档都直接做，只保留一句静默风险提示 |
| 标准 | 默认 | 每次会话至多 1 个红档邀请 |
| 强 | 「带我练」「教练模式」 | 黄档升级为先写后审，红档不主动给退路 |

---

## 安装

一条命令，在 Claude Code 会话里直接跑：

```
/plugin install ai-coding-coach --marketplace jackeyloveseven/ai-coding-coach
```

之后用 `/plugin` 看状态、更新、卸载。装好后新开一个会话即可，无需其他配置——skill 会在你写代码、改代码、调 bug、看训练日志、设计实验时自动生效。

<details>
<summary><strong>不想用插件？也可以克隆 skill 目录</strong></summary>

个人级（所有项目可用）：

```bash
git clone https://github.com/jackeyloveseven/ai-coding-coach ~/.claude/skills/ai-coding-coach
```

Windows PowerShell：

```powershell
git clone https://github.com/jackeyloveseven/ai-coding-coach "$env:USERPROFILE\.claude\skills\ai-coding-coach"
```

项目级（只在这个仓库生效）：

```bash
git clone https://github.com/jackeyloveseven/ai-coding-coach .claude/skills/ai-coding-coach
```

> 这种方式只装到 `ai-coding-coach` **一个** skill，`/coach-drill` 不会跟着装上——要它就还是用插件装。另外 clone 方式不会自动更新，得自己 `git pull`。

</details>

---

## 目录结构

```
ai-coding-coach/
├── .claude-plugin/
│   └── marketplace.json                  # 插件清单，支持 /plugin install 一条命令安装
├── .github/workflows/
│   ├── test.yml                          # CI：ubuntu + windows 两个平台跑测试
│   └── pages.yml                         # 把 site/ 发到 GitHub Pages
├── site/index.html                       # 介绍页（单文件，无构建步骤）
├── SKILL.md                              # 常驻 skill：分档逻辑、三档做法、强度与预算
├── skills/
│   └── coach-drill/SKILL.md              # /coach-drill：显式触发的练习会话
├── references/                           # 两个 skill 共用，按需加载
│   ├── training-run-literacy.md          # 训练日志、指标、实验状态、故障分诊
│   ├── reviewing-ai-output.md            # 审查五步、AI 常见失误模式、改动地图、学习桩
│   ├── experiment-design.md              # 事前记录、消融设计、论文复现协议
│   ├── question-bank.md                  # 出题原则、题型、按等级选题、种子题
│   ├── mastery-ledger.md                 # 掌握等级、间隔复习、摸底、学习卡
│   └── practice-menu.md                  # 先写后审、验证四件套、静默错误清单
├── scripts/
│   └── ledger.py                         # 掌握度台账（仅标准库）
└── exptool/                              # 配套工具：训练实验的统一入口
    ├── exp                               # 命令入口（bash）
    ├── progress/
    │   ├── generic.py                    # 通用进度读取器（--json 给 exp report 画图用）
    │   └── report.py                     # exp report 的渲染器：自包含 HTML，图是手写的 SVG
    └── tests/                            # 本地就能跑，不需要集群
```

参考文件按需加载，不一次全读。

---

## 台账脚本

```bash
python3 scripts/ledger.py record dpo-loss pass --note "答对 beta 的作用"
python3 scripts/ledger.py record attention-mask fail --note "mask 方向写反"
python3 scripts/ledger.py record grad-norm-reading pass --level 3   # 证据很强时直接指定等级
python3 scripts/ledger.py due --limit 3    # 到期的复习项
python3 scripts/ledger.py show             # 全部主题与调档建议
python3 scripts/ledger.py card             # 导出可粘贴的学习卡
```

台账默认在 `~/.ai-coding-coach/ledger.json`，可用环境变量 `COACH_LEDGER` 改位置。读到损坏的文件时会报错并停止，不会覆盖它。

掌握等级：

| 等级 | 含义 |
|---|---|
| 0 | 还没掌握 |
| 1 | 能读懂 |
| 2 | 能预测（跑之前能说对 shape、loss 量级、输出形态） |
| 3 | 能独立写 |
| 4 | 能找 bug、能教别人 |

**证据必须是你做出来的**——答对自测、预测准、先写后审差异小、bug hunt 找到。自己说「我懂了」不算。

---

## 配套工具：exptool

`references/training-run-literacy.md` 讲的是「怎么读训练日志、怎么判断实验状态」。`exptool/` 是那套方法的执行入口——把启动、查看、续跑实验收在一个 `exp` 命令里。

设计上只有两条原则：

1. **每条命令执行前都打印它背后真正跑的命令**（灰色的 `+ ssh ...`）。复制下来自己改着用，熟了以后不用这个工具也能干。
2. **读数看趋势，不看单步**。把整段训练切成若干段比较均值。

它还会读实验目录下的 `PLAN.md`（事前记录），把**判据**印在指标正上方。结果出来之后再定「涨多少算有效」，几乎总会得出「有效」；把判据摆在数字旁边，就没法自欺。没有 `PLAN.md` 时 `exp plan <名字>` 按六项生成模板。

曲线本来就是图的东西，用表格看等于盯单步。`exp report <名字>` 把一次运行渲染成一份**单文件自包含的 HTML**——零外部引用，断网也能双击打开：趋势曲线（细线是逐步原始值，粗点线是分段均值）、8 段均值表、健康检查，以及判据的参考线。判据认得出指标和数值就画线，认不出就退化成图上方的一条标注带，不会瞎画；而当参照是从本次数据里推出来的时候，报告会写明「它不是判据本身，读数仍以 PLAN 里那句为准」。

它是**脱敏的通用版**——主机名、共享盘路径、奖励服务地址全部走配置文件。本地就能试，不需要集群：

```bash
cd exptool
cp runs.conf.example runs.conf
./exp list && ./exp status demo-sft
```

细节和「哪些验证过、哪些没有」的清单见 [`exptool/README.md`](exptool/README.md)。

---

## 设计取舍

几条有意为之、可能看起来反直觉的决定：

- **绿档不做教学。** 学 API 语法、调 matplotlib 样式，这些不增值。教学是噪音，只会让人烦。
- **教学不是关卡。** 用户明确要答案就给。教练的价值在于让你出手，不在于拦着你。
- **检查点不是固定尾巴。** 没有值得说的就不加，宁缺毋滥。
- **一次只抓 1–2 个点。** 列十条等于没列。
- **校准信任比显得专业重要。** 技术论断会标明是「确定」「经验规则」还是「我不确定」。教错比不教更糟。
- **AI 自己的错也是教材。** 出错时直接承认，讲清错在哪，把它变成一次审查练习。

---

## 当前阶段

**早期版本。** 这份 skill 是在实际使用中逐步长出来的，很多判断来自个人经验而非系统验证，欢迎按你自己的情况改。

几个已知的粗糙处：

- 分档标准是经验性的，不同方向（CV / NLP / 推荐 / 语音）的「红档」范围会不一样。
- 掌握等级的判定依赖教练的主观观察，没有客观基准。
- 目前主要面向扩散模型 / RL 后训练方向的训练实验场景，其他场景需要自己调。
- 题库和静默错误清单远没有覆盖完。

欢迎 issue 和 PR。如果你在某个方向上试出了更好的分档或更好的题，尤其欢迎。

---

## 许可

[MIT](LICENSE)。拿去改、拿去用、拿去商用都行，保留版权声明即可。
