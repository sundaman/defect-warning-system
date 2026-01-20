# Defect Warning System - Technical Deployment Handbook

## 1. 核心算法机制与调优 Know-How 🧠

本系统基于 **Adaptive CUSUM** 算法，针对工业制造场景进行了深度定制。以下是运维团队必须掌握的核心知识。

### 1.1 监控类型差异 (Yield vs Parameter)
MES 必须正确区分 `item_type`，否则会导致严重的误报或漏报。

| 类型 | 标识 (`item_type`) | 适用场景 | 算法理论依据 | 默认行为 |
| :--- | :--- | :--- | :--- | :--- |
| **良率类** | `yield` | Pass/Fail 计数，如 "良率", "测试通过率" | **二项分布 (Binomial)**<br>方差完全由均值决定 ($\sigma^2 = p(1-p)/n$)。理论上不可调整。 | 对样本量 (UPH) 非常敏感。UPH 越低，容忍波动越大。 |
| **参数类** | [parameter](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/arl_calculator.py#179-221) | 连续数值，如 "电压", "尺寸", "温度" | **正态分布 (Normal)**<br>方差基于历史数据实测统计。 | 需要"学习"历史波动 ($\sigma$)。 |

> **关键经验**：如果有良率数据表现出"超高离散度"（Overdispersion，实际波动远大于二项分布理论值），请将其 `item_type` 强制设为 [parameter](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/arl_calculator.py#179-221)。这允许算法学习真实的宽方差，从而抑制误报。

### 1.2 UPH 标准化与惩罚机制 (Crucial!)
算法对样本量 (UPH) 极度敏感。
*   **Base UPH**: 系统需要一个"标准产能"作为基准（默认 500）。
    *   *原理*: $H_{dynamic} \propto H_{base} \times \sqrt{UPH_{base} / UPH_{curr}}$
    *   当当前产能远低于基准产能时，统计波动会自然增大。为防止误报，算法会自动放宽报警门限 ($h$)。
*   **惩罚强度 (Penalty Strength)**:
    *   在低产能 (Low UPH) 期间，我们支持 3 种宽容度配置：
        1.  **Strict (1.0)**: 标准物理模型。产能每降一半，门限严格放宽 $\sqrt{2}$ 倍。
        2.  **Moderate (0.6)**: 适度宽容。
        3.  **Relaxed (0.3)**: 极度宽容。即使产能很低，门限也不会放得太宽（此时更相信数据质量）。
    *   *建议*: 默认使用 1.0。如果发现夜班/换线期间误报多，可调低至 0.6 或 0.3。

### 1.3 冷启动策略 (Cold Start)
对于新接入的 [parameter](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/utils/arl_calculator.py#179-221) 类项目，系统没有历史数据。
*   **旧策略**：默认 $\sigma=1.0$。导致系统过于敏感，刚上线就疯狂报警。
*   **新策略 (当前)**：默认 $\sigma=3.0$。
    *   **行为**：前 24-48 小时内，系统处于"宽容模式"，只抓取极端的偏移（>3倍标准差）。
    *   **自动收敛**：随着数据积累（约 50-100 个点后），算法会自动计算出真实的 $\sigma$，检测精度逐渐提升至正常水平。

---

## 2. MES 集成接口规范 🔌

系统采用 **Push (推送) 模式**。MES 需在每次测试结束或每批次数据生成后，调用以下接口。

- **URL**: `POST /api/v1/data/ingest`
- **Content-Type**: `application/json`
- **并发建议**: 100万项场景下建议使用批量推送接口(如有)或在 MES 端做微批次聚合。

### Payload 示例
```json
{
  "items": [
    {
      "item_name": "Voltage_Rail_3V3",
      "item_type": "parameter",  // 或 "yield"
      "value": 3.29,             // 检测值 或 良率(0-1.0)
      "uph": 1200,               // 当前小时产量 (权重因子)
      "timestamp": "2023-10-27T10:00:00", // ISO 8601，建议 UTC
      "meta_data": {             // 供看板过滤用，强烈建议提供
        "station": "Post-SMT",
        "product": "Phone-X",
        "line": "L03"
      }
    }
  ]
}
```

---

## 3. 数据存储与容量规划 💾

### 3.1 核心数据表
数据库中主要维护两张表（数据量完全不同）：
1.  **DetectionRecord (历史轨迹表)**: 
    *   **内容**: 每次 API 调用的完整记录 (原始值 + 算法计算结果)。
    *   **保留策略**: **滚动保留 30 天**。系统每日后台自动清除过期数据。
2.  **ItemState (算法记忆表)**:
    *   **内容**: 每个检测项的"学习成果" (Baseline, Std, CUSUM Score)。
    *   **数据量**: **恒定**。100万个检测项 = 100万行。

### 3.2 容量估算 (100万监控项场景)
假设场景：100万个检测项，采样频率 1次/小时。

*   **日数据量**: $1,000,000 \times 24 = 2,400$ 万行/天。
*   **单行大小**: 约 300 Bytes (包含索引)。
*   **存储需求**:
    *   每日增量: ~7.2 GB
    *   **30天全量**: **~220 GB**
*   **建议规格**: 配置 **500GB SSD** 存储卷 (留出一倍冗余)。

### 3.3 数据库选型建议
*   **开发/测试 (当前)**: SQLite。
    *   *限制*: 无法支撑 100万项高频并发，仅限 < 5万项使用。
*   **生产环境 (推荐)**: **PostgreSQL 14+** (推荐安装 TimescaleDB 插件以优化时序数据)。
    *   *SOP*: 部署 Docker 时设置环境变量 `DATABASE_URL=postgresql://user:pass@host:5432/dbname`。
    *   系统代码会自动识别该变量并切换数据库驱动，**无需修改任何代码**。

---

## 4. 算法记忆与持久化机制 🛡️

为了防止服务重启导致算法"失忆"（即重新进入冷启动），系统实现了**双重持久化**机制。

### 4.1 机制流程
1.  **每日存档 (Daily Snapshot)**:
    *   即使没有重启，后台任务也会每天将最新的 Baseline 和 Std 写入 [ItemState](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/db/models.py#57-88) 表。
    *   **更新模式**: Upsert (有则更新，无则插入)。对于 100万个项目，数据库中始终维持 100万行状态记录，**不会**因为时间推移而膨胀。
2.  **优雅退出 (Graceful Shutdown)**:
    *   当服务收到停止信号 (SIGTERM/SIGINT) 时，会强制执行一次全量状态保存。
3.  **启动恢复 (Startup Recovery)**:
    *   服务启动时，优先从数据库加载 [ItemState](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/db/models.py#57-88)。
    *   **效果**: 重启后，算法能"记得"重启前最后一刻的参数，无缝衔接，无需重新学习。

### 4.2 残留数据治理
*   **SOP**: 当运维人员调用删除接口 (`DELETE /api/v1/configs/{name}`) 时，系统会自动级联删除该项在 [ItemState](file:///Users/luxsan-ict/.gemini/antigravity/scratch/defect_warning_system/src/db/models.py#57-88) 中的记录。
*   **结果**: 数据库永远保持零"孤儿数据"，维护成本极低。

---

## 5. 策略配置与可视化 (Configuration & UI) 🎛️

我们提供了强大的 Dashboard (默认端口 8000) 供运维人员自助调整策略，无需修改后端代码。

### 5.1 全局策略配置 (Global Policy)
位于 Dashboard 的 **CONFIG** 标签页顶部。这里的配置将作为**默认值**应用到所有**新导入**的监控项。

*   **Target Shift / ARL0**: 决定灵敏度的基准。
*   **Base UPH (新增)**:
    *   全厂标准产能基线。默认为 500。
    *   *作用*: 如果某条线是高速线(1200)或低速线(100)，修改此值可让算法更准确地评估"低产波动"。
*   **Penalty Strength (新增)**:
    *   低产宽容度。默认为 **Strict (1.0)**。
    *   *作用*: 遇到夜班或产能爬坡误报多时，可全局调整为 `Moderate` 或 `Relaxed`。

### 5.2 单项精细调优 (Per-Item Config)
点击对应监控项右侧的 **Edit** 按钮，或者在 **Batch Import** 时指定，可以覆盖全局默认值。

*   **场景**: 
    *   某特定治具 (Fixture) 极不稳定，需要单独放宽 (Relaxed Penalty)。
    *   某关键产品线必须严防死守，需要单独调高 Base UPH 和 Penalty。
---

## 6.  元数据匹配与隔离 (Metadata Isolation) 🏷️

> **版本更新**: 自 V2 版本起，系统支持基于 `Product` / `Line` / `Station` 的多维度数据隔离。这意味着相同的 `Item Name` 在不同的产线或产品上可以由不同的检测器实例在不同的配置策略下运行。

### 6.1 复合键机制 (Composite Key)
系统内部使用复合键来唯一标识一个检测器实例：
`Product::Line::Station::ItemName` (例如: `Phone15::L01::SMT::Voltage_3V3`)

*   **优先级**: 系统优先匹配最精确的复合键。如果未找到，则回退到仅使用 `ItemName` 的全局默认配置 (兼容旧版本)。
*   **大小写**: 系统内部会自动将 Product/Line/Station 转换为小写进行存储和匹配，以避免大小写不一致导致的数据分裂。

### 6.2 接口更新 (API Updates for Metadata)

#### 6.2.1 批量创建 (Batch Import)
**Endpoint**: `POST /api/v1/items/batch-import`
新增 `meta_data` 字段（必填）：

```json
{
  "items": ["Test_Item_A", "Test_Item_B"],
  "meta_data": {
    "product": "Watch9",
    "line": "L-A",
    "station": "Audio_Test"
  },
  "config": { ... } // 可选初始配置
}
```

#### 6.2.2 数据注入 (Data Ingest)
**Endpoint**: `POST /api/v1/data/ingest`
即使是单个点的数据注入，也**必须**包含 `meta_data` 以便正确路由到对应的检测器实例：

```json
{
  "item_name": "Test_Item_A",
  "value": 0.98,
  "timestamp": "...",
  "meta_data": {
    "product": "Watch9",
    "line": "L-A",
    "station": "Audio_Test"
  }
}
```
> **注意**: 如果 `meta_data` 缺失或不匹配，系统可能会为该数据创建一个新的"孤儿"检测器，或者将其归入"全局"检测器，导致配置策略失效。

### 6.3 最佳实践
1.  **Scope Consistency**: 在 **Create Detector** 界面时选定的 Product/Station/Line **必须**与 MES 实际上报的字符串完全一致。
2.  **避免混合**: 不要将在不同 Station 上意思完全不同的两个测试项命名为同一个 `Item Name`，除非你明确知道系统会通过 Metadata 将它们区分开。最好的做法是保持 `Item Name` 的全厂唯一性，或者严格依赖 Metadata 隔离。

