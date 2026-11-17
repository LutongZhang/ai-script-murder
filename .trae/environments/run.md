# 项目运行记录

运行按钮使用 [run.json](run.json) 中 `detective` 动作。依赖和模型配置见 [README](../../README.md)。

## Action: detective

- 前端由 Vite 构建，Python 后端同时提供页面及 `/api`，预览地址为 `http://127.0.0.1:8000`。无需单独启动 5173 服务。
- 需要 Python 3、Node/npm、已安装的前端依赖和已登录的 `traex`。配置明确选择 `traex`，不依赖 Agent 终端里临时设置的 API Key。
- 曾缺少整个 `.trae/environments/run.json`，导致 IDE 无可加载的运行动作；现已保存并校验版本 1 配置。

### 常驻 AI 服务

- 后端现在启动一个 `traex app-server`，通过 stdio JSON-RPC 通信。每个 NPC 使用独立角色线程，成功的后续对话复用该线程；实现见 [traex_session.py](../../backend/traex_session.py)，生命周期和恢复规则见 [README](../../README.md)。
- `GET /api/ai-status` 返回进程是否运行、协议是否就绪、PID、进程启动次数和角色会话数，不返回私人剧本或对话。`ready=true` 只说明握手成功，不能用作真实回复成功的证据。
- 本机 CLI 0.204.1 的 app-server 模式拒绝 `--disable plugin_hooks`，不要照搬 exec 模式的全部启动参数。
- 已验证独立前台进程中的真实 app-server 协议握手。两轮真实私聊验证的首轮在 25 秒内未完成，因此真实多轮记忆仍未验证。协议替身检查已覆盖同一进程多轮、角色隔离、未提交响应恢复、超时、进程退出、重开和资源回收。
- 当前工具启动的后台实例中，常驻 AI 服务仍报告权限不足，页面与状态接口正常。普通用户终端启动后的真实对话尚待验证；不要把权限错误解释成缺少 API Key，也不要放宽沙盒或账号权限来规避。
