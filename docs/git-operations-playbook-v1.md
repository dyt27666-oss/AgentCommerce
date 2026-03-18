# AgentCommerce Git Operations Playbook v1

本手册用于当前阶段（测试与展示）下的稳定提交、里程碑标记、快速恢复。

## 1. 稳定提交规则（Stable Commit Rules）

1. 只在以下条件满足时创建稳定提交：
   - 目标范围测试通过（至少 `py -m pytest -q` 的关键子集通过）
   - `docs/testing-playbook-v1.md` 对应流程可复现
   - 关键证据文件已落盘且可复查（artifact-first）
2. 稳定提交必须是单一目标，不混入无关改动。
3. 提交消息使用固定前缀：
   - `chore(stable): ...`（稳定检查点）
   - `fix(hotfix): ...`（演示期紧急修复）
4. 稳定提交前必须执行：
   - `git status --short --branch`
   - `git diff --stat`
   - `git log --oneline -n 5`

## 2. Tag 规则（Milestone / Stable Tag Rules）

1. 稳定版本统一打 annotated tag，不使用 lightweight tag。
2. 命名建议：
   - `stable/v1-testing-ready`
   - `stable/v1-demo-ready`
   - `milestone/phase7-governance-recovery`
3. 每个稳定 tag 必须可回答：
   - “这个版本能稳定跑什么？”
   - “证据在哪里？”
4. 打 tag 后立即推送：
   - `git push origin <branch>`
   - `git push origin <tag>`

## 3. 分支规则（大改前必须开分支）

### 3.1 `main` 职责

1. 只承载“可展示、可回滚”的稳定状态。
2. `main` 上每次合入都应有明确验收证据或回归结果。

### 3.2 分支命名与适用

1. 新能力/高风险链路：`feat/<topic>`
   - `feat/feishu-live-e2e`
   - `feat/multi-model-council`
   - `feat/demo-evidence-pack`
2. 紧急修复：`hotfix/<topic>`
   - `hotfix/recovery-runner`
3. 文档/流程增强：`docs/<topic>`
   - `docs/git-ops-v1`

### 3.3 哪些改动必须先开分支

1. Feishu 真链路改造（listener/worker/protocol）
2. Council 多模型策略逻辑扩展
3. Recovery runner 行为修改
4. 会影响测试基线或演示路径的代码改动

### 3.4 哪些情况下可直接在当前分支提交

1. 当前就在临时功能分支，且改动只属于该分支目标。
2. 仅文档修正或样例补充，不改变运行行为。
3. 已明确这次提交只做“稳定检查点封板”。

## 4. 如何查看历史（审计视角）

1. 看分支和工作树：`git status --short --branch`
2. 看图形历史：`git log --oneline --decorate --graph --all -n 30`
3. 看 tag 指向：`git show stable/v1-testing-ready --no-patch`
4. 看某提交改了什么：`git show --stat <commit>`

## 5. 如何回到稳定提交

## 5.1 临时查看旧版本（不破坏当前分支）

```powershell
git switch --detach stable/v1-testing-ready
```

返回原分支：

```powershell
git switch main
```

## 5.2 从稳定 tag 拉恢复分支（推荐）

```powershell
git switch -c restore/from-stable-v1-testing-ready stable/v1-testing-ready
```

## 5.3 强制硬回退（仅在确认放弃当前本地改动时）

```powershell
git reset --hard stable/v1-testing-ready
```

## 6. `reset` / `revert` / `restore` 场景表

1. `git restore <file>`：撤销工作区某文件未提交修改（最小影响）。
2. `git reset --soft <commit>`：回退提交但保留暂存内容（重组提交）。
3. `git reset --hard <commit>`：本地分支硬回退到旧点（高风险）。
4. `git revert <commit>`：生成“反向提交”撤销历史，适合已推送场景。

推荐原则：

1. 已推送到远端，优先 `revert`，避免改写公共历史。
2. 仅本地未推送，且确定放弃当前改动，才用 `reset --hard`。
3. 单文件误改优先 `restore`，不要扩大恢复范围。

## 7. 大规模 Bug 时的推荐恢复路径

1. 冻结当前状态并留痕：
   - `git status --short --branch`
   - `git log --oneline -n 10`
2. 从稳定 tag 建恢复分支：
   - `git switch -c hotfix/recover-from-stable stable/v1-testing-ready`
3. 在恢复分支上最小修复 + 最小回归测试。
4. 修复可用后再合回 `main`，并打新 tag：
   - `stable/v1-recovered-<date>`

## 8. 演示前一天 Git 检查清单

1. `main` 是否 clean：`git status --short --branch`
2. 是否已存在可回滚 tag：`git tag --list "stable/*"`
3. 是否能从最新稳定 tag 拉起恢复分支并运行核心路径
4. 是否已推送分支与 tag 到 `origin`
5. 是否保留演示证据路径：
   - `artifacts/testing_playbook_v1/<run_id>/demo_ready_report.md`
   - `artifacts/testing_playbook_v1/<run_id>/demo_ready_summary.json`

推荐一键检查（严格模式）：

```powershell
powershell -ExecutionPolicy Bypass -File tools/council_bridge/pre_demo_git_check.ps1
```

可选参数：

```powershell
powershell -ExecutionPolicy Bypass -File tools/council_bridge/pre_demo_git_check.ps1 -StableTagPattern "stable/*" -RequireCleanTree -RequireUpToDateWithOrigin
```

## 9. 当前阶段推荐节奏（最小可执行）

1. `main` 保持稳定并打 `stable/*` tag
2. 高风险任务全部走 `feat/*` 或 `hotfix/*`
3. 每完成一个“可展示闭环”就创建一个 annotated tag
4. 所有回滚动作优先“拉恢复分支”，最后才考虑 `reset --hard`
