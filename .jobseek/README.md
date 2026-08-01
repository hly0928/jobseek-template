# JobSeek 运行态控制面

`batches/` 是运行态唯一真源。`cache/` 仅是可删除并用 `tools/jobseekctl rebuild-cache --track <track>` 重建的索引，不得用于证明候选人事实。

新批次的 `inputs/` 与 `input_snapshot.json` 保存创建时配置的 Candidate Profile、Criteria、Track Profile、answer/content banks、CV、rules、skills、agents、schemas 和 control code；恢复只校验这些副本。工作区源文件之后可正常修改，只影响新批次。`events.jsonl` 是追加式状态、review/approval 和 gate 事件；`discovery_events.jsonl` 可重建 `discovery_state.json`；`jobs/<job_key>/job_evidence_packet.json` 是唯一、不可覆盖的职位证据包。敏感值不得写入此目录。

`batch_sequence.json` 保存全工作区最近分配的批次序号。新批次由 `jobseekctl preflight --new-batch` 在独占锁内创建，命名为 `<track>-<Perth YYYYMMDD>-<sequence>`；序号至少三位并严格递增 1。`--batch-id` 只恢复已有目录。历史非规范目录保持不变，不参与重置序号。

现代 Job Evidence Packet 必须包含完整广告保存文本、metadata、提取事实与定位、重复检查、冻结规则中每项 hard exclusion 的唯一 evaluation、完整且合计正确的 score components、可在权威事实 registry 中验证的事实 ID、显式稳定的推断 ID 与全部边界、完整 classification inputs、分类、风险、未解决项及 artifact paths。`jobseekctl` 根据批次快照中的 hard-exclusion 定义、分数和 `eligible_threshold` 归约分类；缺失、矛盾或不可判定时拒绝 packet 或归入 `Needs Review`。旧 packet 仍按兼容路径读取。packet 的 `metadata.track` 与 job key 必须匹配 batch；修正只能另开批次工作事件，不能覆盖 packet。

每个赛道唯一可执行的 hard-exclusion 规则 ID 与定义、评分分项和 eligibility threshold 均在 `.jobseek/config.json` 的 `tracks.<track>.assessment` 中。Search Criteria 和 Skills 只引用该冻结配置，不维护第二份可执行规则。

`gate` 事件只接受固定 actor/role。所有新旧可恢复批次的提交都必须经过 `Package Prepared → Awaiting User Review → Submission Ready → Submitted`；review 绑定职位、页面、答案、附件和声明，lead 只能在用户本次明确批准后记录单职位 approval。任何绑定证据或材料哈希变化都会使 approval 失效。`record-gate` 仅用于 `materials_qa` 和 `submission_evidence`；eligibility 与 confirmation audit 必须使用结构化命令，不能通过兼容 gate 自动放行。所有 stop counters 由事件和 discovery 增量推导，调用者提供的 counters 只可作为完全一致的弃用断言。

每个具体 `Needs Review` 问题都有唯一 `reason_id`、独立 fingerprint 和固定
允许决定。运行态为 `pending|remain_paused|resolved|skipped`；
`remain_paused` 后仍可再次 resolve 或 skip。用户补充答案、文件或声明时，
resolution 只清除该 reason 关联的 unresolved item。经验缺口 continue 只
处理对应非强制缺口，不能清除其他 review/blocker。Eligibility audit 以
`pass|pass_with_warnings|fail` 追加版本化 overlay，并明确列出解决的 reason、
unknown rule、unresolved item 或标准 blocker；原 packet 永不覆盖。

每次最终提交 review 都创建唯一 `submission_attempt_id`。review、approval、
submission evidence 和 `Submitted` 必须绑定同一 attempt；首次进入
`Submitted` 即消费批准。`Submitted → Failed` 后必须回到
`Awaiting User Review`，重新记录页面和材料并取得新批准。
Confirmation assessment、audit trigger、结构化 audit result 和 gate 同样
绑定该 attempt。Audit result 仅为
`verified|not_submitted|unresolved`，且只有 `not_submitted` 可进入
`Failed`。连续提交失败按 attempt 最终结果计算；open `Submitted` 不清零，
只有 `Submission Verified` 中断失败序列。

历史 `Submitted → Blocked` 只在携带当前 attempt 的 post-submit 状态下兼容恢复；
它仍可继续同一 attempt 的 confirmation assessment/audit。`unresolved` 保持
暂停，不能计为完成、创建新 attempt 或 finalize。

Eligibility trigger 具有不可变 `trigger_id` 和单调版本；audit 与 gate 保存完整
trigger set/version。新增 trigger 或新证据会使旧 gate 失效，必须由新 audit 覆盖全部
当前 trigger 后才能继续 materials/submission。

Discovery frontier 只有 `exhausted` 和 `saturated` 可正常完成；`active`
表示仍可搜索，`blocked` 表示暂停并等待恢复。停止目标触发后运行
`discovery-drain`，将尚未 claim 的候选人幂等记录为
`deferred_due_to_batch_stop`，同时保留已 claim/已打开广告的排空义务。
现代 `fully_assessed` candidate 必须唯一关联 job key、通过验证的 packet
以及至少已到 `Assessed` 的匹配状态；`validate`、counters 与 finalize 使用
同一关联校验。

完整广告打开后确认的过期、无法读取、已知重复或已申请 listing 必须附
reason/evidence，并机械映射到 `Expired`、`Withdrawn` 或 `Duplicate`。
它们清除 open work，默认不计入 `fully_assessed_ads`。

Agent-call no-yield 熔断按 worker role 计算。总预算、role circuit 或单职位
重试耗尽会由 `check-stop` 返回可恢复 pause；只有用户明确授权后，lead
才能用 `resume-agent-calls` 记录 reset/有限扩展。冻结的原始 policy 保留，
并为 drain、confirmation 和安全收尾预留调用能力。

Retry exhausted 仅表示该 role/job 仍有未完成工作且最后允许的调用失败、无产出或未
完成目标；最后一次 productive completion 若已越过该 role 的阶段边界，不会再触发
exhausted。Schema-v1 无 manifest policy 时使用固定 `legacy_v1_defaults`；首次
resume 仅在 manifest 源 hash 未变时建立 batch-local compatibility facts 和安全升级
agent project，漂移则 fail closed。早期 runtime-v1 批次也会在首次恢复时生成一次性、
带哈希的安全升级项目；之后 track 配置、Skills、agent 配置与控制脚本均从批次本地
运行副本读取。`preflight`/`runtime-context` 返回的 `worker_runtime.project_root`、
环境和 `control_entrypoint` 是 worker 的唯一合法启动合同。提交记录归档先追加
attempt-scoped intent，再幂等协调 archive、Tracker 与 Run Log，最后追加完成事件；
中断后用完全相同请求继续。`validate` 会应用 JSON schemas 并检查跨事件 attempt、
gate、retry、frontier 和 finalized 不变量，且不静默修改批次。
