# habit

这是一个围绕“下午防滑坡 + 低阻力重启”场景的 AI 执行监督助手项目仓库。

当前仓库已整理出第一轮项目交付物，后续开发请优先以需求文档为准，而不是直接回到零散想法。

## 文档入口

- [原始想法](C:\Users\1\Desktop\habit\原始想法.md)：最初灵感和问题背景。
- [需求总览](C:\Users\1\Desktop\habit\需求总览.md)：当前唯一的活需求文档。
- [范围摘要](C:\Users\1\Desktop\habit\docs\01-范围摘要.md)：MVP 范围、边界和假设。
- [架构说明](C:\Users\1\Desktop\habit\docs\02-架构说明.md)：推荐技术架构和核心组件设计。
- [实施计划](C:\Users\1\Desktop\habit\docs\03-实施计划.md)：并行开发 lane、集成顺序和 review gate。
- [核心流程伪代码](C:\Users\1\Desktop\habit\docs\04-核心流程伪代码.md)：提醒链、反馈、规则和 AI 生成的逻辑骨架。
- [验证清单](C:\Users\1\Desktop\habit\docs\05-验证清单.md)：验收标准、关键路径测试和失败场景检查。

## 当前 MVP

第一阶段只做单用户、自用验证版，目标是验证这条链路是否成立：

1. 先判断今天是工作日、普通休息日还是节假日。
2. 按对应模板生成当天提醒链。
3. 工作日重点覆盖 15:00、15:20、15:40、17:30、21:15 这条主链。
4. 晚上生成收口建议，避免继续过热。

## 默认技术方向

在没有额外约束的前提下，当前文档默认推荐：

- 前端：React + Vite + PWA
- 后端：FastAPI
- 定时任务：APScheduler
- 存储：SQLite
- 推送：先做可插拔适配层，MVP 首接 Bark
- AI：大模型 API + 规则兜底

## 建议开发顺序

1. 锁定共享数据模型和接口契约。
2. 搭建后端提醒调度与通知链路。
3. 搭建 H5/PWA 反馈页。
4. 接入规则引擎和 AI 下一步生成。
5. 做日志、验证和自用闭环。

## 当前代码实现

第一版已落地“模板调度内核”，代码在 [habit](/C:/Users/1/Desktop/habit/habit/__init__.py)：

- `resolve_day_type`：判断工作日、周末、节假日
- `select_schedule_template`：选择对应模板并支持工作日回退
- `materialize_day_schedule`：将模板物化为当天提醒计划
- `prepare_day_schedule`：打通“日期 -> 模板 -> 当天提醒计划”主链
- `build_default_templates`：提供三套默认模板示例

当前已经继续扩展为一个可运行的本地 MVP 服务，主要包括：

- [api.py](/C:/Users/1/Desktop/habit/habit/api.py)：FastAPI 接口和反馈页
- [service.py](/C:/Users/1/Desktop/habit/habit/service.py)：主业务编排，覆盖模板、提醒、反馈、收口、日志
- [rules.py](/C:/Users/1/Desktop/habit/habit/rules.py)：三档动作规则引擎和滑坡恢复协议
- [planner.py](/C:/Users/1/Desktop/habit/habit/planner.py)：本地上下文规划器，作为 AI 层的可运行替身
- [storage.py](/C:/Users/1/Desktop/habit/habit/storage.py)：JSON 持久化状态仓库
- [defaults.py](/C:/Users/1/Desktop/habit/habit/defaults.py)：默认健康规则

## 运行方式

查看今天会生成什么提醒计划：

```powershell
python -m habit
```

启动本地 API 服务：

```powershell
uvicorn habit.api:app --reload
```

启动后可访问：

- 首页：`http://127.0.0.1:8000/`
- 模板列表：`http://127.0.0.1:8000/api/templates`
- 通知 outbox：`http://127.0.0.1:8000/api/notifications/outbox`

一个最小触发顺序示例：

```powershell
curl -X POST "http://127.0.0.1:8000/api/day-schedule/prepare?target_date=2026-06-03"
curl -X POST "http://127.0.0.1:8000/api/reminders/run-due?now=2026-06-03T15:00:00"
curl "http://127.0.0.1:8000/api/notifications/outbox"
```

运行当前单元测试：

```powershell
python -m unittest discover -s tests -v
```

## Android

仓库现在额外包含一个标准 Android 子工程，位置在 [android](/C:/Users/1/Desktop/habit/android/settings.gradle.kts)。

- App 模块：`android/app`
- 入口 Activity：[MainActivity.kt](/C:/Users/1/Desktop/habit/android/app/src/main/java/com/example/habit/MainActivity.kt)
- GitHub Actions workflow：[android-apk.yml](/C:/Users/1/Desktop/habit/.github/workflows/android-apk.yml)

这个 Android 工程当前是一个最小可打包壳工程，重点是：

- 结构适合 GitHub Actions 直接构建 Debug APK
- 不依赖本仓库现有 Python 服务才能编译
- 后续可以再把提醒、日志、模板管理等真实移动端功能接进去

GitHub Actions 会在 `push`、`pull_request` 或手动触发时执行：

```text
gradle assembleDebug
```

并上传产物：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```
