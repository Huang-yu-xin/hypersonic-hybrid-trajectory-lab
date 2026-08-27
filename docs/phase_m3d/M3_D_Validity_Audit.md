# M3-D Validity Audit — Theory-Gate-to-Pipeline Evidence

> **Schema:** `raretopo-m3d-v0` ｜ **Date:** 2026-08-27
> **Machine records:** gate_audit_m3d.json（D7）、labels_corrected_v2.json、m3d_layer_a_v1.json 及各 ablation 批次(results/ untracked per policy)

## 1. 审计矩阵

| 层 | 断言 | 证据 |
|---|---|---|
| 前置链 | H3/M1/M1-D/M2/M3-v0 五 tag 解析哈希逐一符合冻结记录 | gate audit `parent_tags_unchanged_incl_M3_v0`(含 32b2856) |
| 构造 | 装配确定性(锚 seed2026)+ 选择锁 vs 归档 | D1 交叉验证 ALL MATCH;56+48 态合法性全 PASS |
| 标签 | 规则执行与锁定 spec 一致 | **修复审计**:两缺陷(margin/sup­port gating)被 §36 测试捕获→纯重算 sidecar→Freeze v2;细节见 Methodology §2 |
| 隔离 | online API 无 oracle 面 | test_m3d_no_oracle_leakage(源扫描+签名白名单) |
| 控制器 | 与 M3-v0 parity | test_m3d_controller_parity_with_m3 bitwise(g_hat/μ̂/D̂/CI/ESS/决策) |
| 运行 | 无缺格、合法、CRN、闭合 | 192 格唯一;非法臂诊断见 §3;CRN 重放 bitwise;ΣL=M₂ 全臂 0 违例 |
| 账目 | 320k/120k 每试验恒定 | 双口径字段全检通过 |

## 2. 已知例外(如实保留)

1. **非法比较器臂**:`c000@0.55` 的 ALWAYS_SHRINK 臂 min-eig=0.450<0.5(0.55·e^{-0.20})。处理=审计层把该臂从固定规则聚合**排除**(不作为方法价值证据;raw batch 不动),非修复非删除;若 Always-Shrink 为 BEST_FIXED 该规则将失去此态证据——本批 BEST_FIXED 实为 Always-Widen,故聚合影响有限但仍如实列出(合法性策略选 not count illegal proposals as value evidence,继承 frozen checker 纪律)。
2. **HOLD 类固有难度**:±3% 邻域内的三态均匀几何导致 CI-sign 在该类动作频率过高(recall 0.25)——这是控制器的有限样本性质,不是数据缺陷;§33 D-B 显示低 ESS 边界带反而更准。

## 5. Freeze provenance verification(freeze audit 2026-08-27)

- **v1** commit `d9a0e16`(2026-08-27 17:16:43 +0800)→ **v2** 随 `ad4484c`(17:36:30)落盘——两者均**早于任何 online adaptive trial**(D6 于同日更晚提交);
- v1 被 v2 取代的原因(明示):reference-label implementation 不符合已冻结 prereg semantics(`label_state` 的 margin 定义与 support 门控两处实现偏差);修复为对存储批数组的纯函数重算,sidecar `m3d_labels_corrected_v2.json` 记录逐代源哈希与翻转清单;
- **未改变项核对**:controller、thresholds、raw reference samples、selection rule 逐一原样——两代池工件当前 sha256 与 sidecar 记录一致(byte-exact verification TRUE);
- Freeze JSON/MD 与 Methodology/Final Report 关于 v1→v2 的表述保持同一口径。

## 6. 合法分母政策(illegal comparator arm)

`c000@0.55` 的 ALWAYS_SHRINK 臂 min-eig=0.450 违反 frozen floor ⇒ 该 trial 在 D-A 及一切固定规则统计中于所有通道排除(不当 tie/base/win);该限制记录为 protocol limitation;benchmark state 不改选。派生表已按此口径重生成(`total_illegal_trials_excluded=8`)。

## 7. 全量测试证据

`python -m pytest -q`:**1144 passed / 0 failed,451.14s,exit 0**(2026-08-27;含 §36 的 16 项 M3-D 结构套件;在线试验开始前采集)。

## 4. 诚实性追踪(pre-online 阶段)- Amendment-1 与其触发归因(dose-response 单调、SHRINK 域在网格外)全部基于已存 raw 数据;
- label_state 两处缺陷在任何在线 Trial 之前发现并回溯重算,决策机制「纯函数重算」不触碰任何抽样流;
- 未发生:阈值放宽、状态删除、结果驱动的基准调整(v2 选择仍为逐字 first-8)。
