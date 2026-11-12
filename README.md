# 局中人：多剧本 AI 陪玩剧本杀

先在剧本库选择故事，再扮演其中一名角色，其余角色由 AI 陪玩。你也拥有秘密、人际关系、私人线索和个人目标，可以选择凶手角色，隐瞒经历、寻找盟友或引导讨论。角色私聊、公聊和投票理由都通过本机 traex 调用真实模型实时生成，没有预设角色台词。

目前内置两个完整四人本：

| 剧本 | 场景 | 角色 | 时长 |
| --- | --- | --- | --- |
| 雨夜封锁 | 暴雨封闭旅馆，财产纠纷与失踪刀具 | 孟秋、林策、苏曼、周峻 | 30–60 分钟 |
| 末班来信 | 雪夜停驶列车，上锁包厢与一封责任书 | 顾鸣、许知遥、唐梨、陆行舟 | 40–70 分钟 |

剧本库会显示每个故事的当前角色与阶段，点击“继续这一局”接回进度。每个剧本的游戏状态、手牌、投票、NPC 记忆和对话分别保存，切换剧本不会清空另一局。“重开本剧本”只清空当前故事。当前存储仍在后端进程内，重启后端会清空所有剧本进度。

前端使用 React 18 + Vite，页面拆为剧本库、选角、游戏布局、读本、私聊、搜证、公开讨论及线索组件。`useGame` 统一处理 HTTP 操作与 AI 等待队列，`useNarration` 管理逐字显示和语音。前端显示文案、席位数量和搜证次数从当前剧本状态读取。

## 怎么玩

1. **选本、选角与读本**：在剧本库打开故事，领取任一角色的私人剧本，阅读经历、秘密、关系和个人目标。
2. **双向私聊**：你可以找角色交换信息、试探或争取合作；角色也会根据自己的目标、关系和当前局势主动邀请你。接受后由对方先开口，可以婉拒或稍后回复。各自的对话记录和输入草稿独立保留。
3. **搜证**：从八个地点选择最多三个搜索。线索进入你的手牌，其他人也拥有各自的线索。
4. **公聊**：AI 轮流主动发言，后发言者会回应前面的讨论。你可以公开手牌、发言或听他们继续聊，也可以返回私聊。公开线索对全桌可见。
5. **秘密指认**：提交你的一票，AI 分别依据自己的经历、记忆和公开材料投票，不能读取其他人的票。
6. **复盘**：所有票同时揭晓；显示唯一最高票指认（平票则没有唯一指认）、固定案件真相及你的个人目标完成情况。

AI 调用失败时，已完成的发言保留，当前角色仍在等待队列中。点击“继续 AI 发言”或“继续指认”即可接上。首次公聊及每一轮追加公聊会依次调用三名角色，需等待多次推理。

第二至第四幕，页面在交流间隙自动让 AI 逐个判断是否主动私聊，每个角色每幕最多一次。未回复的邀约会暂停新邀约，选择稍后回复可留待处理。角色可以选择暂不联系，不保证每轮都有人找你；判断和开场都由真实模型生成。邀约本身不交付线索，接受并成功生成开场后才可能私下收到线索。婉拒、暂缓和邀约状态只提供给对应角色，不进入公聊；指认阶段会使未处理邀约过期。离开游戏页面会暂停判断，返回后接上；主动判断失败时点击“重试邀约判断”，不会自动无限重试。

## 配置与启动

后端使用 Python 3 标准库，无须安装模型 SDK。默认调用本机 `traex`，使用其已登录身份及 `Doubao-Seed-2.1-Turbo` 模型。

### traex（默认）

```sh
traex login status
traex models --json
npm --prefix frontend install
npm --prefix frontend run build
NPC_AI_PROVIDER=traex python3 -u backend/server.py
```

如果尚未登录，先执行 `traex login`。可以设置以下环境变量覆盖默认值：

```sh
export NPC_AI_PROVIDER=traex
export NPC_AI_TRAEX_COMMAND="/Users/bytedance/.local/bin/traex"
export NPC_AI_MODEL="Doubao-Seed-2.1-Turbo"
export NPC_AI_TIMEOUT=120
```

模型 ID 使用 `traex models --json` 中的 `config_name`（没有时使用 `name`）。后端启动一个常驻的 `traex app-server --listen stdio://` 子进程，通过 JSON-RPC 与其通信。每个 AI 角色第一次发言时创建独立 `thread`，之后私聊、公聊和投票复用该线程，并以 JSON Schema 约束最终回答。其他角色的私聊不会进入这个线程。

常驻会话自动保留已完成的对话，不需要每轮重新启动 CLI 或重复发送全部历史。后端仍保存角色的记忆摘要、私聊与公开讨论，作为游戏状态和恢复依据；每轮发送最新角色可见上下文。后端用唯一响应 ID 确认上一轮是否实际保存，拒绝复用含有未提交回答的线程。回答结构无效、超时或进程退出后会清理服务状态；下一次请求根据后端已保存的记忆重建会话。不同剧本有独立游戏 ID；切换到另一剧本推理时重新创建 CLI 服务及线程，返回原剧本时用它自己的已保存记忆恢复，避免沿用另一故事的上下文。这个实现不提供跨后端重启的存档。

调用限定为纯角色对话，禁用工具、插件和项目说明加载，拒绝协议中的工具、权限和交互输入请求；不会自动授权模型操作文件或执行命令。CLI 的 SQLite 状态及日志写在本服务的临时目录，登录身份仍使用本机配置；关闭后端时清理子进程与临时目录。当前实现依赖 CLI 的实验性 app-server 协议，更换 CLI 版本后需要验证兼容性。

不需要单独设置 API Key；模型推理通常仍由 TRAE 的远端服务完成，需要网络及可用账号额度。

常驻进程省去了每轮启动 CLI 的成本，模型生成仍需等待网络服务。默认单轮超时为 120 秒，可以通过 `NPC_AI_TIMEOUT` 调整。整个 CLI 通信采用串行调用，避免同一角色的上下文交叉。

之前每轮启动 `traex exec` 的方案在受限后台环境报过 `failed to initialize in-process app-server client: Permission denied (os error 13)`。切换常驻服务不会放宽该环境的权限；启动失败时仍会明确报错。可以访问 `GET /api/ai-status` 检查 `running`、`ready`、进程 PID、创建过的进程数及角色会话数。`ready=true` 仅代表协议握手成功，真实推理成功需另行验证。

最终回答优先取协议标记为 `final_answer` 的消息。解析兼容纯 JSON、BOM 和单个 JSON Markdown 代码块（可带说明文字）；截断或多代码块回答仍会拒绝保存。解析失败时，后端终端记录字符数、代码块数量及 JSON 错误行列，不打印角色秘密或模型思考内容；`/api/ai-status` 的 `lastError` 保留本次错误。修改后端代码后，需要在启动它的终端按 Ctrl+C，再执行启动命令加载修改。

JSON 或结构校验失败时，在同一个角色线程中最多让模型重新生成一次，仍须通过全部线索归属和投票校验才保存。两次调用共用 `NPC_AI_TIMEOUT` 时限，权限、网络和超时失败不触发格式重试。`/api/ai-status` 的 `formatRetries` 记录格式重试次数，`lastFormatError` 保存最近错误的角色 ID、阶段、字符数和解析位置，不包含回答原文；重试后成功时这些诊断仍保留。

### OpenAI 兼容 HTTP 服务

需要服务支持 Chat Completions，以及模型支持 `response_format: {"type": "json_object"}`。

在运行后端的终端中设置：

```sh
export NPC_AI_PROVIDER=openai
export NPC_AI_BASE_URL="https://api.openai.com/v1"
export NPC_AI_MODEL="你的模型 ID"
read -s "NPC_AI_API_KEY?请输入模型 API Key: "
export NPC_AI_API_KEY
python3 backend/server.py
```

以上输入 Key 的命令适用于 macOS 默认的 zsh。兼容服务请将地址替换为服务商的 API 基础地址（通常包含 `/v1`），模型 ID 使用账号实际可用的名称。也支持 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL`；`NPC_AI_*` 优先。`.env.example` 仅说明配置项，程序不会自动加载 `.env` 文件。

浏览器打开 `http://127.0.0.1:8000`。若修改了前端，在 `frontend` 目录执行 `npm install` 和 `npm run build`，然后刷新。

开发时可分开运行后端和 Vite，以启用 React 热更新：

```sh
# 一个终端
NPC_AI_PROVIDER=traex python3 -u backend/server.py
# 另一个终端
npm --prefix frontend run dev
```

打开 Vite 输出的地址（默认 `http://localhost:5173`），`/api` 自动代理到 `http://127.0.0.1:8000`。后端监听可用 `NPC_HOST` / `NPC_PORT` 配置；后端使用其他端口时，在启动 Vite 的终端设置 `NPC_BACKEND_URL`。`.env.example` 中的后端变量仍需要通过终端显式导出。

HTTP 模式的 API Key 仅由后端环境变量读取，不发送到前端。未登录、配置缺失、网络失败或模型返回无效结构时，界面显示错误，本轮不会增加对话、修改记忆或解锁证据。

## 角色与状态

- 每个 AI 角色仅收到公共背景、自己的私人剧本与手牌、全桌公开线索、公聊记录、自己与玩家的私聊及独立记忆。玩家的秘密和手牌、其他角色的私人档案和私聊、其他人的投票不会放入上下文。
- 凶手档案包含自己的作案过程；无辜角色只知道自己的行为与目击。模型应维持既有口供，并根据实际对质选择隐瞒、辩解或承认。
- 模型输出角色发言、情绪、更新记忆、愿意分享的证据 ID 和投票选择。后端校验证据归属；私聊分享仅将线索交给玩家，公聊分享才公开给全桌。主持流程、搜证材料和案件真相固定。
- 重复提及已经取得的物证不会重复解锁，也不会使整轮对话失败。适配器兼容纯 JSON 和完整的 Markdown JSON 代码块，其他无效输出仍拒绝保存。
- 每个剧本拥有独立的进程内游戏状态；所有浏览器仍共享同一剧本的一局，不提供多用户隔离。模型调用使用所属剧本的状态快照，调用期间该局发生重置或另一轮对话提交时，旧回答返回 409，不覆盖新状态。操作请求始终携带 `scriptId`，避免切换界面后误操作另一剧本。

## 添加剧本

所有故事在 `backend/scripts/*.json` 中，启动时自动加载，不需要修改 React 页面或游戏流程代码。复制一个现有 JSON，修改唯一 `id`、公开简介、角色、线索、地点、时间线和真相，再重启后端即可出现在剧本库。完整字段说明见 [剧本配置说明](backend/scripts/README.md)。

加载时校验重复 ID、凶手角色、线索引用、角色关系、目标类型及搜证次数，配置错误会指出文件并阻止启动。剧本库接口只返回公开元数据与进度，角色秘密只在选角后返回给对应玩家；固定真相在第六幕才返回。

事实一致性和线索透露的合理性依赖模型遵守角色指令，结构校验并不能保证每句话都符合案情。更换模型后应进行多轮试玩，评估角色性格、抗诱导能力及对质节奏。

## HTTP 接口

`GET /api/scripts` 返回剧本库及公开进度；`GET /api/state?scriptId=last_letter` 读取指定剧本的玩家可见状态；`GET /api/ai-status` 读取常驻 AI 服务状态，不返回角色秘密或对话。以下操作均使用 `POST` 和 JSON 请求体，所有请求可带 `scriptId`，省略时默认 `rain_lock`，兼容原接口：

| 接口 | 请求体 | 用途 |
| --- | --- | --- |
| `/api/start` | `{"scriptId":"last_letter","roleId":"secretary"}` | 选角入局 |
| `/api/reset` | `{"scriptId":"last_letter"}` | 只清空指定剧本 |
| `/api/advance` | `{}` | 推进下一幕（读本至公聊） |
| `/api/question` | `{"npcId":"guest","question":"…"}` | 独立私聊 |
| `/api/initiative` | `{"scriptId":"last_letter"}` | 当前幕下一名角色判断是否主动邀约 |
| `/api/invitation-response` | `{"scriptId":"last_letter","invitationId":"…","decision":"accept"}` | 接受、婉拒（`decline`）或暂缓（`later`）邀约 |
| `/api/search` | `{"locationId":"machine"}` | 搜索地点 |
| `/api/publish` | `{"evidenceId":"ledger"}` | 公开自己的手牌 |
| `/api/discuss` | `{"message":"…"}` | 玩家公聊并排下一轮 AI；空内容让 AI 继续 |
| `/api/ai-turn` | `{}` | 完成队列中一名角色的公聊或秘密投票 |
| `/api/vote` | `{"targetId":"boss_wife"}` | 提交玩家的秘密指认 |

`question`、`ai-turn` 及接受邀约返回 `{reply, state}`；`initiative` 返回 `{invitation, state}`，未邀约时 `invitation` 为 `null`；婉拒、暂缓和其他接口直接返回状态。NPC 开场记录包含 `initiator: "npc"`，`question` 为空，前端不会伪造玩家发言。秘密投票期间 `reply` 为 `null`，投票详情只在第六幕的 `result` 中返回。此 Demo 仅供单人本地试玩，不提供多人会话隔离或持久化存档。
# ai-script-murder
