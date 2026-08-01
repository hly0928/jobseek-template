# 使用 Codex 开始 JobSeek

本模板用于让 Codex 在同一工作区内协助整理候选人资料、搜索与评估职位、制作申请材料、填写申请，并在你逐职位审核和明确批准后完成最终提交。

根 Codex 会话始终是唯一 lead。它可以安排有界的 discovery、exception audit、materials、submission 和 confirmation-audit worker，但 worker 不能继续委派。

> [!IMPORTANT]
> 本模板是需要人工监督的实验性工作流，不是全自动求职服务。
> 你需要对候选人事实、材料真实性、职位选择和每次最终提交负责，并遵守招聘网站和雇主的使用要求。

## 运行要求

* Python 3.9 或更高版本；
* 能读取整个工作区并加载项目 agent 配置的 Codex 环境；
* 需要搜索或填写网页时，使用已有登录状态的浏览器；
* 登录、密码、验证码、CAPTCHA 和账户恢复始终由你本人处理。

`tools/jobseekctl` 只使用 Python 标准库，不需要另外安装 Python package。

本文档中的命令默认直接运行：

```text
tools/jobseekctl ...
```

如果当前系统不能直接执行该文件，可改用：

```text
python tools/jobseekctl ...
```

## Agent 执行默认值

`.codex/config.toml` 将有界子代理的默认模型设为 `gpt-5.6-luna`，reasoning effort 设为 `high`。

不同 Codex 环境支持的模型可能不同。首次使用前应检查 `.codex/config.toml`，必要时改成当前环境实际可用的模型。不得因为普通任务失败、工具失败或输出质量问题而静默切换模型。

模板当前的控制规则只允许在运行时明确报告 Luna 不可用、无法加载或不受支持时，由根 lead 将同一次有界 spawn 重试一次为 `gpt-5.6-terra` 和 `medium`。

## 开始前

1. 复制整个模板目录，或者通过 GitHub template 创建一个新的私人工作区仓库。

2. 将 `JobName/` 重命名为赛道名，例如 `IT/`、`Design/` 或 `Hospitality/`。

3. 编辑 `.jobseek/config.json`：

   * 删除不准备使用的示例或多余赛道；
   * 将 `tracks` 中对应的 `JobName` key 改为实际赛道名称；
   * 更新该赛道所有 `input_paths` 中的目录名称；
   * 配置该赛道唯一可执行的 hard-exclusion 定义；
   * 配置合计为 100 的评分分项；
   * 配置 eligibility threshold；
   * 必要时调整 limits 和 stop conditions。

4. 不要修改 `tools/jobseekctl` 中的脚本常量来配置赛道。

5. 填写以下权威输入，并删除所有占位符：

   * `Profile/Candidate_Profile.md`
   * `<赛道>/Profile/Track_Profile.md`
   * `<赛道>/Templates/Search_Criteria.md`
   * `<赛道>/Templates/Application_Answer_Overrides.md`
   * `Templates/Application_Answer_Bank.md`
   * `Templates/Cover_Letter_Content_Bank.md`

6. 将真实、完整、可复用的基础 CV 保存为：

   ```text
   CV/CV_Plain_Base.docx
   ```

7. 在 Codex 中打开工作区根目录，并确保它能读取该目录下的 `AGENTS.md`、Skills、配置和控制脚本。

8. 需要搜索或填写网页时，连接已有登录状态的浏览器。

9. 如果工作区位于 Git 仓库中，提交前运行：

   ```text
   git status --short
   ```

   确认没有提交私人资料、运行批次、申请材料、证据文件、日志或浏览器数据。

如果你不想手动完成赛道配置和资料检查，可以直接使用下面的首次提示词，让 Codex 协助初始化。

## 首次运行提示词

首次运行的目标是把工作区准备完整，而不是立即搜索或提交职位。

```text
这是我第一次使用这个 JobSeek 工作区。请把根 Codex 会话作为唯一 lead，先阅读 AGENTS.md、START.md、.jobseek/config.json 和相关 JobSeek Skills。

请先协助我完成工作区初始化，不要搜索职位、不要创建批次、不要打开招聘网站，也不要提交申请。

请依次：
1. 询问我要建立的职位赛道名称，将 JobName 目录和 .jobseek/config.json 调整为该赛道，并删除不使用的示例或多余 track；不要修改 jobseekctl 的脚本常量。
2. 和我确认该赛道唯一的 assessment 配置：eligible threshold、每条 hard-exclusion rule ID 及定义，以及合计为 100 的 score components；不要在 Search Criteria 或 Skills 中维护第二份可执行规则。
3. 审查所有必需输入文件是否存在、是否仍有占位符、是否互相冲突，以及 config 中的每条 input_path 是否指向实际文件。
4. 用合并后的少量问题向我收集缺失信息，不要从历史申请、Tracker、日志或模型推断候选人事实。
5. 协助填写或完善 Candidate Profile、Track Profile、Search Criteria、Application Answer Overrides、Application Answer Bank 和 Cover Letter Content Bank。
6. 协助我准备一份真实、完整、可复用的 plain base CV；不得编造，也不得把个人、课程、项目或志愿活动写成就业经历。
7. 将电话和邮箱作为普通候选人联系资料处理。真正敏感的信息不要写入 stdout、日志、事件、报告或模型摘要；如申请时确实需要，由我在网页中手动填写。
8. 运行 preflight 的 dry-run、只读检查和静态验证，列出仍缺少的文件、占位符、冲突和需要我决定的事项。
9. 检查 git status，指出任何不应提交到公开仓库的候选人资料、运行产物或敏感文件，但不要删除我的真实文件。

完成初始化后，请只向我报告：
- 已准备的权威输入；
- 仍缺少的信息或材料；
- 尚未解决的风险；
- 是否已经具备创建首个批次的条件。

在我明确要求前不要创建批次。
```

## 让 Codex 协助准备全部材料和信息

当资料尚不完整，或你希望系统性重做候选人材料时，使用此提示词：

```text
请对当前 JobSeek 工作区做一次“申请准备度”整理。此次只准备权威资料和通用材料，不搜索职位、不创建批次、不填写或提交网页。

请以现有 Candidate Profile、Track Profile、Search Criteria、answer/content banks 和 plain base CV 为起点：
1. 建立一份缺失信息清单，并把问题合并、去重，按阻塞程度排序后询问我。
2. 明确区分就业经历、教育、个人项目、课程项目、志愿活动和其他实际经验，禁止夸大或改写其性质。
3. 准备或完善：
   - Candidate Profile；
   - 赛道 Track Profile；
   - Search Criteria；
   - Application Answer Overrides；
   - Application Answer Bank；
   - Cover Letter Content Bank；
   - plain base CV；
   - 必要的证据索引和“不具备/未知”边界。
4. 对每一项候选人事实标明它来自我的明确陈述还是现有权威文件；不要把广告、网页、历史申请、Tracker、日志、缓存或模型推断当成候选人事实。
5. 检查 CV 与资料库之间是否有矛盾、占位符、无法证明的年限、技能、证书、工作权利、可用性或声明。
6. 电话和邮箱可正常保留在私人工作区中的 Candidate Profile、CV 和申请材料中。真正敏感值不得出现在输出或持久化运行记录中；需要时提醒我手动输入。
7. 完成后运行静态检查，并给出“已就绪 / 仍需补充 / 必须人工决定”三类结果。

修改前保留我的既有真实内容；不要修改历史申请、已完成批次或 Applications 归档。
```

建议提前准备的信息包括：

* 姓名、常用名、电话、邮箱、所在城市及可用于申请的联系信息；
* 工作权利的非敏感事实描述；
* 教育、真实就业、项目、技能、工具和语言；
* 明确没有、未知或不能证明的经验、资质、执照和证书；
* 求职地点、工作方式、工时、薪资、行业和职位边界；
* 可用日期、通知期，以及不能由代理推定的承诺；
* plain base CV；
* 可复用的真实案例、成就及其证据边界；
* 必须由本人决定或手动填写的声明和敏感字段。

不要把身份证件、护照、签证文件、驾照、警方证明、银行、税务、医疗文件、密码、验证码或浏览器 session 数据交给代理自动上传，也不要将它们提交到 Git 仓库。

## 创建首个或新的批次

资料检查通过后，在同一根会话中发送：

```text
请开始一个新的 JobSeek 批次，赛道是 <赛道名>。

先使用 jobseek-preflight-control 流程运行：
tools/jobseekctl preflight --track <赛道名> --new-batch

必须使用工具返回的 batch_id，不得自行编造。确认新批次已经保存并验证 Candidate Profile、Search Criteria、Track Profile、answer/content banks、plain base CV、rules、Skills、agent/config、schemas 和 control code 的不可变快照及哈希。

然后按批次中冻结的配置执行有界 discovery 和普通资格评估。只使用该批次快照中的候选人事实。按 jobseekctl 推导的 counters 和 stop conditions 工作，不要由调用者提供或猜测 counters。

对 Eligible 职位继续准备材料；遇到缺失事实、敏感声明、文档请求或真正需要我决定的问题时暂停并集中询问。任何最终 Submit/Apply/Send 都必须等待我对该职位当前页面、答案、附件和声明进行审核并明确批准。
```

## 后续运行提示词

### 恢复未完成批次

关闭或重开 Codex 后，不要让模型凭聊天记忆继续。使用：

```text
请恢复现有 JobSeek 批次：
- track: <赛道名>
- batch_id: <已有批次ID>

先运行：
tools/jobseekctl preflight --track <赛道名> --batch-id <已有批次ID>

只从该批次自己的 manifest、input snapshot、events、discovery events、job packets 和紧凑状态恢复。不要用当前工作区源文件替换批次快照，也不要把 Tracker、Logs 或历史 Applications 当成候选人事实。

请报告当前阶段、事件推导 counters、未完成 claim、待处理职位、待我回答的问题和下一安全动作，然后继续正常工作流。已完成批次只读，不得恢复写入。
```

### 创建后续新批次

```text
请为 <赛道名> 创建一个全新的 JobSeek 批次。先验证当前权威输入，再运行 preflight --new-batch。新批次应使用当前最新版资料生成自己的快照；不得复用或修改旧批次快照。创建后按正常有界工作流继续。
```

源文件在某个批次创建后仍可正常更新，但这些更新只影响后来创建的新批次。旧批次继续使用自己的冻结快照。

## 常用专项提示词

### 只搜索和评估，不制作或提交

```text
请恢复或创建 <赛道名> 的批次，只进行有界 discovery、完整广告读取、去重和普通资格评估。不要制作材料，不要打开申请表，不要提交。保存 frontier 和 evidence packets，并报告事件推导 counters、Eligible、Skipped、Needs Review 与主要原因。
```

### 只准备某个职位的申请材料

```text
请为 batch <批次ID> 中的职位 <job_key> 准备申请材料。先验证它处于 Eligible 状态、materials ownership 已正确 claim，且所有触发的 exception audit 已通过。

只使用该批次快照和职位 evidence packet 中有依据的事实，准备并视觉检查所需 CV、cover letter 和 application answers，记录 materials_qa 证据与哈希。不要打开申请网页，不要进入 submission，也不要修改权威源文件或历史申请。
```

### 准备申请页面并停在人工审核点

```text
请为 batch <批次ID> 中的职位 <job_key> 执行 submission preparation。

验证 submission ownership、职位身份、材料哈希和未解决项后，使用已登录浏览器填写申请，但不要点击任何最终 Submit/Apply/Send。

准备完成后：
1. 停在最终提交前的页面；
2. 记录当前职位 URL、页面指纹、全部答案、附件和声明的 review bundle；
3. 将状态保持在 Awaiting User Review；
4. 清楚列出让我检查的页面、答案、附件、声明和任何风险；
5. 等待我对这个职位和这个确切 review_id 的明确批准。

不得使用以前的批准、批量批准或推定批准。
```

### 逐职位批准最终提交

只有当你已经亲自查看当前页面、所有答案、附件和声明后，才发送：

```text
我已经查看并确认以下申请的当前最终页面、全部答案、附件和声明：
- batch_id: <批次ID>
- job_key: <job_key>
- review_id: <当前review_id>

我明确批准仅对这个职位、仅对这个未改变的 review 版本执行一次最终 Submit/Apply/Send。

提交前请再次校验当前页面身份、review_id、答案、附件和声明。任何实质变化都立即停止，本批准失效，并重新让我审核。提交后请验证确认页面、确认邮件或申请编号；如果结果不明确，不得盲目重试。
```

这段提示词不是预授权。不能在页面尚未准备好或你尚未完成审核时提前发送。

### 更新未来批次使用的候选人资料

```text
请根据我这次明确提供的信息更新当前权威源文件，供未来新批次使用。不要修改任何现有批次的 input snapshot、events、job packets、历史申请或已完成批次。

更新后运行静态检查，并说明哪些文件改变、哪些候选人事实受到影响，以及为什么现有批次仍继续使用其旧快照。
```

### 检查状态但不继续操作

```text
请只读检查 batch <批次ID>。从 .jobseek/batches 中汇总当前状态、事件推导 counters、active claims、frontiers、各职位状态、待审核/待批准事项和 stop condition。不要搜索、修改文件、打开网页、填写表单或提交。
```

### 安全诊断或修复控制层

```text
这是一项 JobSeek 控制层诊断/修复任务，不是职位搜索或申请任务。请只检查我指定的缺陷，保护候选人事实、历史申请、Applications 和 Completed 批次。

先做只读诊断并说明影响范围。只有在修复确实必要时才最小修改 control/config/schema/tests；不得借此创建批次、搜索职位、提交申请或扩大范围。完成后运行相关测试、静态检查和残留文件扫描。
```

## 重要操作信息

### 文件职责

* `Profile/`、`CV/`、`Templates/` 和 `<赛道>/Profile|Templates/`：新批次的权威输入来源。
* `.jobseek/config.json`：唯一的 track、assessment、limits 和 stop conditions 配置；hard exclusions、score components 和 threshold 只在这里定义。
* `.jobseek/batches/<batch_id>/inputs/`：该批次冻结的输入副本。
* `.jobseek/batches/<batch_id>/events.jsonl`：追加式状态、ownership、review、approval 和 gate 事件。
* `.jobseek/batches/<batch_id>/discovery_events.jsonl`：可重建 discovery 状态的增量事件。
* `<赛道>/Tracker/` 和 `<赛道>/Logs/`：旧版兼容和历史视图，不保证无损重建批次，也不是候选人事实来源。
* `<赛道>/Applications/`：仅保存已经直接确认提交成功的归档。

### Preflight

只检查、不创建批次：

```text
tools/jobseekctl preflight --track <赛道名> --new-batch --dry-run
```

创建新批次：

```text
tools/jobseekctl preflight --track <赛道名> --new-batch
```

恢复批次：

```text
tools/jobseekctl preflight --track <赛道名> --batch-id <已有批次ID>
```

Preflight 会拒绝缺失 CV、缺失必需文件、残留占位符和无效配置。新批次创建后，修改工作区源文件不会破坏旧批次；只有批次自身快照缺失、损坏或不再通过完整性验证时才会 fail closed。

### 人工提交闸门

代理可以填写和准备申请，但不能替你完成审核。每个职位必须依次经过：

```text
Package Prepared
→ Awaiting User Review
→ 当前 review bundle
→ 用户对该职位和 review_id 的明确批准
→ Submission Ready
→ Submitted
→ Submission Verified
```

职位、页面、答案、附件、声明或相应证据发生实质变化时，已有批准立即失效。

每次记录新的 submission review 都会建立独立的 submission attempt。批准在该 attempt 首次进入 `Submitted` 时被消费。若提交失败，必须回到 `Awaiting User Review`，重新记录当前页面和材料、重新审核并重新批准；旧批准不能用于重试。

如果填写阶段发现新的答案、文件、声明或选择问题，应为每个具体问题记录独立 `reason_id` 并进入 `Needs Review`。暂停后可以分别 resolve 或 skip，但任何 resolution 都不能顺带清除其他问题。

Confirmation assessment、异常 trigger、audit result 和 gate 必须绑定当前 submission attempt。Confirmation audit 只能记录：

* `verified`
* `not_submitted`
* `unresolved`

只有 `not_submitted` 可以开始失败后的新 attempt。旧 attempt 的确认不能用于当前提交。

旧批次若出现 `Submitted → Blocked`，仅把它当作当前 attempt 的 confirmation-pending 恢复状态：继续使用同一 review、approval、submission evidence 和 `submission_attempt_id`。

`unresolved` 只能暂停，不能计为完成、finalize 或创建新 attempt；只有 `verified` 或 `not_submitted` 才能闭环。

Eligibility audit trigger 使用不可变 `trigger_id` 和 version。新增 trigger 或新证据会使旧 gate 失效，必须重新 audit 并覆盖完整 trigger set。

Retry exhausted 只针对仍有未完成 role 工作且最后允许调用未成功的 scope。最后一次 productive completion 越过 role 阶段边界后，不应误触发暂停。

Schema-v1 恢复使用固定 legacy defaults，并只在源 hash 未变化时建立 batch-local compatibility facts；发生漂移时会提前 fail closed。

### Agent-call 暂停与恢复

如果 `check-stop` 报告 agent-call budget、no-yield circuit 或 per-job retry 暂停，不要绕过限制。

只有在你明确授权后，lead 才能使用事件化的 `resume-agent-calls` reset 或有限扩展；原批次 policy 和所有扩展记录都会保留。

如果总 agent-call budget 已经耗尽，仅 reset role 或 job scope 并不会增加总额度。恢复时必须显式提供正数额度，例如：

```text
tools/jobseekctl resume-agent-calls \
  --track <赛道名> \
  --batch-id <批次ID> \
  --worker-role <角色> \
  --additional-calls <增加数量> \
  --user-authorized \
  --evidence-path <授权证据文件>
```

如果是 role-wide circuit，必须按 CLI 提示执行 role-wide reset；不要把 job-scoped reset 当成整个角色已经恢复。

### 敏感信息与公开仓库

电话和邮箱是普通候选人联系资料，但不代表它们适合提交到公开仓库。

真正敏感的信息不得通过 CLI 返回给模型，也不得写入 stdout、事件、日志、缓存、manifest、报告或摘要。如果网页必须填写且没有安全的非模型通道，Codex 应暂停并请你直接在浏览器中输入。

`.gitignore` 只能降低误提交风险，不能替代提交前检查。公开 GitHub 仓库中应保留未填写的模板，而不是已经填入真实候选人资料的工作区。

提交前至少运行：

```text
git status --short
```

必要时再运行：

```text
git diff --cached
```

### 浏览器限制

* 登录、密码、验证码、CAPTCHA 和账户恢复由你处理。
* 最终审核必须基于当前真实页面，而不是旧截图或聊天描述。
* 用户批准后，提交 worker 仍必须在实际点击前重新检查页面身份、答案、附件和声明。
* 如果页面在批准后出现新字段、新声明、附件变化或其他实质变化，必须停止并建立新的 review。
* 如果确认页面、邮件或申请编号不明确，应记录异常并停止，不得再次点击提交。

## 一次完整运行的推荐顺序

1. 使用首次提示词初始化工作区。
2. 使用材料准备提示词补齐权威资料和 plain base CV。
3. 先运行 preflight dry-run。
4. 创建不可变批次快照并开始 discovery。
5. materials worker 仅处理已验证为 Eligible 的职位。
6. submission preparation 填写页面，并停在 `Awaiting User Review`。
7. 你查看当前页面，并逐职位发送明确批准提示词。
8. worker 在点击前再次核对当前页面，然后执行一次提交。
9. 提交后验证确认；确认成功才进入 `Applications/`。
10. 使用事件推导 counters 判断停止，并在所有 claim 和 confirmation 已终结后完成批次。
