# 剧本配置

每个 `*.json` 是一个独立故事。后端启动时扫描这个目录，前端从 `/api/scripts` 获取剧本列表。新增文件后重启后端即可，无需改前端组件。

每个可玩剧本的选角页都提供“凶手模式”，调用 `/api/start-killer` 后由后端按该本 `killer` 选择玩家角色，不需要把凶手 ID 提前放进公开目录。状态的 `playMode` 为 `killer` 或普通选角的 `roleplay`；只用于玩家界面，不把玩家的凶手身份告诉 AI。两种入口共用同一剧本进度与流程，凶手模式不自动公开真相、改变案情或授予其他角色的私密信息。已有进度需重开后重新选择模式；`awaiting_materials` 剧本的凶手入口保持禁用。

进入 `kind: accusation` 阶段前，状态返回 `accusationReadiness`（其余阶段为 `null`），包含已搜地点数、未搜地点数、当前阶段真正可搜索次数、公共线索数和提醒。新增公开线索不满两条时提示判断材料可能不足；这是提醒阈值，不是证据充分性的判断，也不会暴露未取得的线索。即使无提醒，仍需确认结束调查：`/api/advance` 提交 `confirmAccusation: true`，或调用 `Game.advance(confirm_accusation=True)`。不强制搜完、公开线索或达成个人目标；当前待发言角色仍必须先完成。普通阶段推进不需要确认，未设指认阶段的剧本不受影响。

以 [雨夜封锁](rain_lock.json) 或 [末班来信](last_letter.json) 为旧格式完整示例，[拉文内尔庄园](ravenel_manor.json) 为可配置玩法示例。所有内容是固定案情、角色材料和流程规则，NPC 发言仍由模型实时生成。

| 顶层字段 | 含义 |
| --- | --- |
| `id` | 唯一剧本 ID，HTTP 操作使用这个值 |
| `title` / `subtitle` / `summary` | 公开标题、副标题及共同背景。不能包含未公开的凶手身份 |
| `opening` | 可选的完整公共开场，交代舞会或事件背景、玩家为何在场、案发经过和当前局势；缺省使用 `summary`，玩家与 AI 接收同一份开场 |
| `tags` / `duration` / `difficulty` | 剧本库展示信息 |
| `schemaVersion` | 当前为 `2`；旧本缺省时自动规范化 |
| `theme` / `coverText` | `rain`、`train`、`manor` 或 `western`；可选封面文字 |
| `locationLabel` | 搜证区域称呼，例如旅馆、列车 |
| `searchLimit` | 本局总搜索次数上限，阶段可以另设更小的配额 |
| `mode` | 阶段、能力与进入阶段的线索发放配置，缺省用原六幕模式 |
| `availability` | `status: ready` 或 `awaiting_materials`，`note` 说明材料完整性；待补齐条目不能开局 |
| `source` | 可选原作信息：`title`、`publisher`、`url`、`language`、`completeness`、`note`，都应是公开信息 |
| `victim` / `killer` / `truth` | 死者姓名、凶手角色 ID、最终固定真相。`killer` 和 `truth` 不进入公开简介 |
| `publicEvidence` | 初始对所有人公开的证据 ID 数组 |
| `timeline` | 时间线：`id`、`time`、`title`、`detail`、`unlocked_by_default`。只有标记公开的条目进入共同背景 |
| `evidence` | 证据：`id`、`title`、`summary`、`detail`；可选 `kind: material`（默认物证材料）或 `testimony`（记忆证词，不能伪装成实物） |
| `locations` | 地点：`id`、`name`、`description`、`evidence`；可选 `phases` 限定在哪些阶段 ID 开放 |
| `npcs` | 包含所有可选角色，玩家占一个席位，其余由 AI 扮演 |

每个角色字段：

| 字段 | 含义 |
| --- | --- |
| `id` / `name` / `role` / `public_profile` | 唯一 ID、姓名、身份和公开简介 |
| `private_secret` | 该角色自己的秘密，不能塞入他不知道的全局真相 |
| `facts` | 确实发生且该角色知道的经历、目击 |
| `strategy` | 角色的隐瞒、合作、对质策略；不要预写回答台词 |
| `initial_emotion` | 冷静、烦躁、戒备、紧绷、防守、松动、配合、慌张之一 |
| `book.intro` | 玩家领取的私人剧本开篇 |
| `book.approach` | 可选的玩家应对原则、披露取舍与认知边界；读本和全人物复盘显示，缺省使用 `strategy`。不要预写台词 |
| `book.relationships` | 其他所有角色 ID 到关系说明的映射，不包含自己 |
| `book.starting` | 开局持有的私人证据 ID 数组 |
| `book.search` | 在带 `distributeSearch: true` 的阶段进入时，该 AI 角色取得的线索；玩家通过地点搜索获得 |
| `book.goals` | 每条包含 `title`，以及可核验的 `condition` 或 `type: narrative` |

玩法配置示例：

```json
{
  "id": "my_mode",
  "label": "两轮搜证与交流",
  "phases": [
    {"id": "read", "kind": "reading", "label": "读本", "objective": "领取身份", "actions": []},
    {"id": "mingle", "kind": "exchange", "label": "私聊", "objective": "交换经历", "actions": ["private", "initiative"]},
    {"id": "search", "kind": "search", "label": "搜证", "objective": "搜索两处", "actions": ["search", "private"], "searchLimit": 2},
    {"id": "table", "kind": "discussion", "label": "公聊与补查", "objective": "讨论并补查", "actions": ["search", "publish", "discuss", "private", "initiative"], "searchLimit": 2, "distributeSearch": true},
    {"id": "vote", "kind": "accusation", "label": "指认", "objective": "秘密投票", "actions": ["vote"]},
    {"id": "reveal", "kind": "reveal", "label": "复盘", "objective": "揭晓", "actions": []}
  ]
}
```

- `id` 是唯一阶段 ID；标签可重复，类型可重复，阶段数可变化。`kind` 为 `reading / exchange / search / discussion / accusation / reveal`。
- `actions` 是当前阶段允许的操作：`private / initiative / search / publish / discuss / vote`。同一基础操作可以在多个阶段开启；`initiative` 必须同时允许 `private`。
- 读本必须首阶段且不开放操作；复盘必须最后且不开放操作。如有秘密投票，必须独占倒数第二阶段，投票结束自动进入复盘。没有投票的流程可以手动推进到复盘，此时不显示投票判定。
- 搜索过的地点整局不能重复。`searchLimit` 顶层为全局上限，阶段内为独立配额，两者都必须有剩余。
- 阶段可配置 `publicEvidence: ["证据ID"]`，或 `privateEvidence: {"角色ID": ["证据ID"]}`，进入时一次发放；后者不进入前端公开规则。`distributeSearch` 只给 AI 发 `book.search`，玩家不自动取得。
- 开放 `discuss` 的阶段进入时排一轮 AI 公聊；随后玩家可以继续公开发言或排新一轮。
- 时间线中未公开的条目及真相只在 `reveal` 返回。AI 始终仅接收自身角色资料和当前可见线索。

组合目标示例：

```json
{
  "title": "取得旧处方并避免它公开",
  "condition": {
    "all": [
      {"check": "evidence_held", "evidenceId": "prescription"},
      {"check": "evidence_hidden", "evidenceId": "prescription"}
    ]
  }
}
```

条件支持 `all`、`any`、`not` 组合；叶子检查为 `not_accused`、`vote_killer`、`evidence_public`、`evidence_hidden`、`evidence_held`、`private_contact`（需要 `roleId`）。`private_contact` 核验玩家与指定角色发生过实际私聊，不会把邀约或婉拒算作交流。开放叙事目标如 `{"title":"保护母亲的住处","type":"narrative"}` 在复盘标为“自行回顾”，不自动计分。

支持的个人目标：

| `type` | 达成条件 | 额外字段 |
| --- | --- | --- |
| `avoid_accusation` | 自己不是唯一最高票被指认者（平票视为未被唯一指认） | 无 |
| `vote_killer` | 自己的秘密投票指向该剧本凶手 | 无 |
| `publish_evidence` | 指定证据最终已公开给全桌，不限由谁公开 | `evidenceId` |
| `hide_evidence` | 指定证据最终没有公开给全桌 | `evidenceId` |

旧 `type` 目标自动转换成上述条件，保留原判定结果。同一剧本内各类型 ID 不能重复，所有证据引用必须存在，`killer` 必须对应可选角色。新本至少需要两名角色，界面席位数量随角色列表变化。公共信息、私密材料和角色目击应彼此一致；结构校验不会自动判断作案时间线是否合理。

`awaiting_materials` 条目只需要公开元数据、公开角色简介、说明和无操作的资料模式，不需要伪造 `killer / truth / book`。拿到完整材料后填全案情和玩法，改为 `ready`，通过完整校验后才能开局。`Way out West` 当前就是资料条目；交易、战斗、中毒等机制需要后续扩展通用动作与状态规则，不能直接填一个未知动作或让模型宣称执行。

后端仅保存内存状态。多个故事可以来回切换并继续；重开只影响指定故事，重启后端则清空所有故事。不同用户或浏览器访问同一剧本仍共享一局。

## 生成与原作适配的完整性核对

个人剧本不能仅用人物摘要代替。玩家选择任意角色后，都应能回答：我是谁、与死者和其他人有什么关系、为什么来到现场、此前亲历了什么、现在发生了什么、我想保护或争取什么。公共开场、玩家读本、AI 角色上下文与最终复盘必须共同覆盖这些信息。

所有人共同经历的场景应明确写入公共开场、公开时间线或初始公开线索，例如仪式举办地点及桌子、杯子的位置。NPC 可以隐瞒自身行动，不能通过改写共同场景辩解；历史生成的错误地点不能成为新设定。

适配已有原作时，逐页阅读完整材料，并逐角色核对下列映射；没有拿到完整材料的条目保持 `awaiting_materials`。结构校验只检查字段和引用，不能证明语义上没有遗漏，仍需人工对照。

| 原作内容 | 系统字段与核对要求 |
| --- | --- |
| 开场、共同事件 | `opening`、公开时间线与 `publicEvidence`；交代地点、日期、仪式或事件的含义、案发前后顺序，不提前解释真凶或未知机制 |
| Who you are / 身份 | `book.intro`、`public_profile`、`relationships`；保留年龄、身份、受邀或服务原因、长期关系、装扮等有助于扮演和推理的信息 |
| Your secret / 秘密 | `private_secret` 与必要的私人线索；保留金额、日期、利益与隐瞒原因，只给知情角色，不能塞入主持人全知解答 |
| What you know / 已知信息 | `facts` 与 `book.starting`；逐条保留时间、地点、目击情境、看到与没看到的内容；传闻、怀疑和确定事实分清楚 |
| Your goals / 目标 | `book.goals`；保留保护身份、关系、生计及取得物品等支线。投对票不能替代“理解往事”；不可核验的目标使用 `narrative` |
| If accused / 应对 | `book.approach` 与 `strategy`；转为披露取舍和应对原则，不给固定回答台词；辩解不能改写为无罪证明 |
| 凶手专页 | 仅凶手的秘密和事实；保留旧事、动机、准备、手法、时间和风险，不把他不知道的其他人行动塞给他 |
| 主持人解答、线索与时间线 | `truth`、全部时间线、物证和角色证词；核对证据链是否能闭合、误导线索是否可解释、重要材料是否有实际获得路径 |
| 人数变体、主持提示、原版机制 | 核对当前适配采用的人数和流程，并明确差异；不把原版未实现的行为说成系统已支持 |

完成后逐一选择所有角色检查实际返回的读本，确认私人事实未进入其他角色的公开资料、未解锁时间线未提前泄露；复盘应揭示全部角色背景、秘密、已知信息、目标和应对原则。检查完整线索列表时，应包含本局未发现的材料，并明确这不代表玩家当局已经获得。

本次《拉文内尔庄园》核对使用 `research/script_sources/ravenel_complete_kit.pdf`（12页）及同一发行方页面提取的 `ravenel_complete_kit.txt`，两者是同一来源的不同载体。页码对应：1规则，2公共开场，3伊尔玛，4加斯帕，5埃莱奥诺尔，6莱斯特拉德（含凶手专页），7巴西尔，8维克图瓦，9奥菲莉，10奥斯卡，11主持人解答与人数变体，12时间线。本地采用完整8人版本，原版三幕自由交流映射为读本、私聊、两轮搜证与公聊、指认、复盘。原文奥斯卡听见的“后天，永久离开”与妻子11月1日车票存在表面日期差异，分别保留为所闻片段和本人行程，不擅自统一，也不让奥斯卡知道车票日期。

《Way out West》本地只有介绍及背景 PDF，尚缺完整角色本、个人目标和秘密、道具、主持人解答及相关机制材料，不能据此补写成忠于原作的完整可玩版本。
