# 工业缺陷预警系统开发任务清单

## 阶段一：需求分析与架构设计 📋
- [x] 理解算法原理与代码结构
- [x] 评估全局参数可行性
- [x] 设计通用数据接入接口 (MES)
- [x] 设计报警输出接口
- [x] 设计运维管理端原型与接口
- [x] 编写详细设计方案与实施计划

## 阶段二：核心引擎开发 🚀
- [x] 构建自适应检测引擎核心
- [x] 实现多维度检测项并发处理
- [x] 开发数据缓存模块（用于提供报警前后背景数据）
- [x] 实现参数自动持久化与加载机制

## 阶段三：API 与运维系统开发 💻
- [x] 开发 MES 数据接入 API
- [x] 开发运维管理前端 API (项目维护、参数设置)
- [x] 开发报警推送服务 (模拟实现)
- [x] 开发服务状态监控模块

## 阶段四：部署与验证 🛠️
- [x] Docker 容器化配置
- [x] 编写单元测试与模拟并发测试
- [x] 撰写接口文档
- [x] 系统演示与交付

## 阶段五：系统对齐与验证 (新增) ⚖️
- [x] 编写算法一致性验证脚本
- [x] 执行 [defect_test_data_v2.csv](file:///Users/luxsan-ict/.opencode/Defect%20Early%20Warning/data/generated/defect_test_data_v2.csv) 对齐测试
- [x] 生成差异分析报告

## 阶段六：算法参数调优 🎛️
- [x] 修改 [AdaptiveCUSUMDetector](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/adaptive_cusum.py#9-363) 支持 `penalty_strength`
- [x] 更新 API 接口支持配置下发
- [x] 更新交付文档嵌入参数说明图

## 阶段七：运维看板与功能增强 📊
- [x] **数据层**：引入 SQLite 数据库，持久化存储检测历史数据
- [x] **算法层**：支持 `cooldown_periods` 参数配置化
- [x] **API层**：开发 `GET /api/v1/history` 接口 (支持时间/项目筛选)
- [x] **前端**：开发可视化 Dashboard (使用 ECharts，支持多图联动)

## 验证与压力测试 (Post-Dev) ✅
- [x] 执行 10,000 条真实测试数据的全链路回放 (API -> DB -> Dashboard)
- [x] 验证高并发数据注入下的系统稳定性 (Success: 100%)

## 阶段八：看板详情交互与多维筛选 🖥️
- [x] **数据库**：升级 [DetectionRecord](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/db/models.py#7-56) 模型，增加 `station/product/line` 字段
- [x] **API**：更新 [DataIngestRequest](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py#56-63) 和 [history](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py#388-427) 接口支持新字段
- [x] **前端**：增加 Station/Product/Line 筛选栏
- [x] **交互**：实现预警记录点击弹窗 (Context Modal)，展示前后30周期趋势

## 最终验收与问题修复 (Final Fixes) 🔧
- [x] 修复报警时 CUSUM 归零的 Bug ([adaptive_cusum.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/adaptive_cusum.py))
- [x] 优化弹窗查询范围至 48 小时，确保展示完整趋势 ([index.html](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/web/index.html))
- [x] 重新注入 10,000 条数据并验证所有修复生效

## 阶段九：用户体验优化 (UX Improvements) 🎨
- [x] **数据库**：为筛选字段 (`station`, `product`, `line`) 添加索引以优化查询
- [x] **API**：开发 `/api/v1/options` 接口，提供动态筛选项
- [x] **前端**：将输入框升级为动态下拉菜单 (Select/Datalist)

## 阶段十：参数配置管理功能 (Configuration Management) ⚙️
- [x] 验证配置热更新机制 (Config Hot Reload) <!-- id: 11 -->
    - [x] 编写验证脚本 [scripts/verify_config_hot_reload.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/scripts/verify_config_hot_reload.py)
    - [x] 调试解决 `h_value` 不更新的问题 (Added property setters & recalculation)
    - [x] 修复 API 路由优先级问题 (Global config shadowed by Item config)

## 阶段十二：监控项管理与体验优化 (Item Management & UX) 🚀
- [x] 后端实现 Delete Item 功能 <!-- id: 12 -->
    - [x] [persistence.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/persistence.py): update [delete_item_config](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/persistence.py#33-37)
    - [x] [manager.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/manager.py): update [remove_detector](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/manager.py#64-69)
    - [x] [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py): add DELETE endpoint
- [x] 前端 UI 改进
    - [x] Import Modal: Rename tabs to "文本粘贴" / "文件上传"
    - [x] Item List: Add Search/Filter input
    - [x] Item List: Add Delete button and logic

## 阶段十三：高级参数配置 (Advanced Parameters) 🛠️
- [x] 后端支持动态修改 `mu0` 和 `monitoring_side` <!-- id: 13 -->
    - [x] [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py): Update [ItemConfigUpdate](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py#208-216) model
    - [x] [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py): Update [update_item_config](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py#267-292) logic
    - [x] [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py): Update [GlobalConfigUpdate](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py#229-234) for `monitoring_side`
    - [x] [manager.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/manager.py): Apply global `monitoring_side` in [get_or_create_detector](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/manager.py#33-63)
- [x] 前端 UI 支持
    - [x] Edit Modal: Add `mu0` input
    - [x] Edit Modal: Add `monitoring_side` select (Upper/Lower/Both)
    - [x] Item List: Display `monitoring_side`
    - [x] Global Config: Add `monitoring_side` selector

## 阶段十四：全局配置重构与引导式导入 (Refactor Global Config & Guided Import) 🛡️
- [x] 后端逻辑重构 <!-- id: 14 -->
    - [x] [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py): [update_global_config](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py#235-266) stops propagating changes to active detectors (Default only).
    - [x] [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py): `batch-import` accepts `config_overrides`.
- [x] 前端交互重构
    - [x] Import Modal: Add "Batch Configuration" section (collapsible).
    - [x] Import Modal: Populate with current Default Config.
    - [x] UI: Rename "Global Policy" to "Default Policy (For New Items)".
- [x] **后端**：实现 `/api/v1/configs` GET/PUT 接口
- [x] **前端**：实现 SPA 导航栏与 Dashboard/Configuration 视图切换
- [x] **前端**：开发配置列表表格与编辑弹窗
- [x] **集成**：验证参数修改的实时生效性

## 阶段十一：监控项管理与全局策略优化 (Item Management & Global Policy) 🚀
- [x] **API**：实现 `PUT /api/v1/configs/global` 全局策略更新接口
- [x] **API**：实现 `POST /api/v1/items/batch-import` 批量导入接口
- [x] **前端**：重构配置页，置顶 Global Config 设置
- [x] **前端**：实现导入模态框 (支持文本粘贴和 CSV 上传)
- [x] **集成**：验证批量导入后的自动配置应用
- [ ] **UI优化**：完善 Default Policy 面板
    - [x] 拆分 Cooldown 和 Side 为独立设置项
    - [x] 增加每个参数的详细说明与使用建议
    - [x] 显示预估 h 值 (Based on Shift & ARL0)
- [x] **功能扩展**：监控项删除功能
    - [x] 后端：实现 `DELETE /api/v1/configs/{item_name}`
    - [x] 后端：实现 `POST /api/v1/configs/batch-delete`
    - [x] 前端：实现单项删除按钮与确认
    - [x] 前端：实现多选与批量删除
- [x] **运维特性**：数据保留策略
    - [x] 后端：实现 `cleanup_old_data` 定时任务 (保留30天)
    - [x] 启动项：在 [main.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/api/main.py) startup 事件中挂载
- [x] **算法优化**：参数类冷启动配置
    - [x] 核心：将 Cold Start 默认 Std 从 1.0 调整为 3.0 (Hardcoded)
- [x] **系统健壮性**：算法状态持久化 (SQLite方案)
    - [x] 模型：[models.py](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/db/models.py) 新增 [ItemState](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/db/models.py#57-88) 表
    - [x] 核心：[AdaptiveKUpdater](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/k_updater.py#21-280) 支持状态导出/导入 (std, k)
    - [x] 核心：[AdaptiveCUSUMDetector](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/core/adaptive_cusum.py#9-363) 支持状态导出/导入 (baseline, S+, S-)
    - [x] 存储：[ConfigStore](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/persistence.py#5-48) 改为操作 DB [load_all_item_states](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/persistence.py#54-75) / [save_item_states](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/persistence.py#76-108)
    - [x] 调度：实现每日自动存档 & 服务关闭时存档
    - [x] 启动：服务启动时尝试恢复历史状态

## 阶段十五：元数据隔离与UI重构 (Metadata Separation & UI Revamp) 🏷️
- [x] **核心架构**：支持 Product/Line/Station 复合键 <!-- id: 18 -->
    - [x] 后端：更新 `_generate_detector_key` 支持元数据组合
    - [x] 后端：修复后端配置持久化时的元数据丢失问题 (Fix persistence bug)
    - [x] 存储：确保 `meta_data` 字段正确写入 `item_configs.json`
- [x] **配置列表优化 (Config List UI)** 🎨
    - [x] 布局重构：分离过滤器行与操作按钮
    - [x] 功能：增加 Product/Line/Station 独立搜索框
    - [x] 修复：解决过滤器变量冲突导致的列表空白问题
    - [x] 显示：列表正确解析并显示 Metadata 列 (Uppercase)
    - [x] 交互：增加 "Clear Filters" 功能
- [x] **导入功能增强**
    - [x] UI：增加 Product/Line/Station 必填输入框
    - [x] 验证：添加必填项校验逻辑
    - [x] 接口：对接后端 `batch-import` 传输元数据
- [x] **文档更新** 📚
    - [x] 更新 `TECHNICAL_HANDBOOK.md` 包含第6章 "元数据匹配与隔离"
    - [x] 明确 MES 接口规范与最佳实践
