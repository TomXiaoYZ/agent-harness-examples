Minimal task cards and a dependency-free preflight checker.  
Keep handoffs in the repository and review in two stages.  
Limit task size, allow two rounds, and track cost per accepted change.

# 双 Agent 协作的最小示例

这套模板用于一个 Agent 定义任务和验收、另一个 Agent 执行的协作方式。
例如由 Claude Code 规划验收，Codex 实现。只需 Python 3.9+ 标准库，无需安装依赖或联网。

## 三条规则

1. **交接物放仓库里。** 将目标、授权、验收标准与回执保存为文件，使用仓库已有的版本管理方式，
   让执行方与验收方对照同一版任务卡。源码用路径和符号引用。
2. **卡有大小上限，最多两轮。** 默认上限为 12 KB（12288 字节），派发前先自检。
   第二轮仍未通过时拆卡或交负责人决定；扩大授权要写新卡。检查器负责静态规则，轮次由人按回执与判决核对。
3. **看每个被接受改动的成本。** 为每张卡记录规划、实现、验收及返工的总成本与最终判决。
   同一统计期内的总成本除以被接受改动数，才是每个被接受改动的成本；未被接受的尝试也计入分子。
   同时记录时间、轮数与计费口径。输入、输出、缓存的单价可能不同，不能把 token 数直接当费用；
   未知写“未知”，接受数为零时写“无法计算”。本示例不采集用量。

## 目录

```text
README.md                   使用说明
templates/task-card.md      任务卡模板
templates/verdict.md        两阶段验收判决模板
scripts/check_card.py       卡自检命令
tests/test_check_card.py    命令行回归测试
LICENSE                     MIT 许可
```

## 从复制到验收

在本示例目录执行：

```sh
mkdir -p docs/tasks
cp templates/task-card.md docs/tasks/example.md
python3 -B scripts/check_card.py docs/tasks/example.md
```

刚复制的卡会报 `FAIL placeholder`。填写所有尖括号占位符；无适用项写“无”，
保留必需二级标题，再运行同一命令。输出 `OK`、退出码为 0 后再派发。
改动预算默认 300 行；确实需要超过时，在“改动预算”节补充 `理由：` 和具体原因。

执行方先写“必须通过的新测试”，记录失败，再实现到通过并交回回执。
验收方复制判决模板，先只读卡写检查清单，再看 diff 核对证据；将判决记录到卡的“轮次”节。

检查模板本身与运行回归测试：

```sh
python3 -B scripts/check_card.py --template templates/task-card.md
python3 -B -m unittest discover -s tests -v
python3 -B scripts/check_card.py docs/tasks/example.md --max-bytes 12288
```

## 自检规则与退出码

用法：`python3 scripts/check_card.py CARD [--max-bytes N] [--template]`。
`N` 是非负整数，按原始 UTF-8 文件字节数计算，恰好等于上限可通过。

| 规则 | 报错条件 |
| --- | --- |
| `size` | 文件字节数超过上限 |
| `missing-section` | 缺少目标、授权、验收标准、改动预算、必须通过的新测试、边界、完成定义、回执格式中的任一二级标题 |
| `pasted-code` | “回执格式”节之外的围栏代码块超过 15 行；支持反引号和波浪线围栏，计数不含开闭围栏 |
| `placeholder` | 残留尖括号包住的短文本；内文长 1–40 个字符，不全为空白、不含 `/`、`:` 或换行 |
| `budget` | “改动预算”节出现大于 300 的数字加“行”，但同节没有“理由”二字 |

`templates/` 目录下的文件自动跳过占位符检查；其他位置的模板可加 `--template`。
填写后的卡应放在 `templates/` 之外，检查时不要加该开关。两种豁免均不影响其他规则。
“回执格式”的子标题仍属于该节；遇到下一个一级或二级标题，长代码块豁免结束。
未闭合围栏的内容计到文件末尾。围栏内的标题不算必需小节。

| 退出码 | 输出 |
| --- | --- |
| 0 | stdout 输出 `OK` |
| 1 | stdout 逐条输出 `FAIL 规则名: 说明` |
| 2 | 参数或文件读取错误，stderr 输出一行 `ERROR: 说明` |

检查器只核对文本规则，不判断验收是否充分、理由是否成立或任务是否获得授权；这些由验收清单确认。
测试临时文件只写入本示例目录，并在测试结束时清理；`-B` 避免生成字节码缓存。

示例为通用模板，不含任何实际项目信息

## 系列文章

1. [让 Claude Code 当经理、Codex 当工程师：152 张任务卡之后我学到的](articles/01-claude-code-manager-codex-engineer.md)（[掘金版](https://juejin.cn/post/7707644445541826569)）
2. [写进说明的规则会被忘，写进钩子的不会：但钩子也会冤枉人](articles/02-hooks-over-instructions.md)
