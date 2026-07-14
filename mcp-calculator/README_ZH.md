# Medical Calculator MCP Service

**中文版** | [English](README.md)

医学计算器 MCP 服务实现。

## 🚀 项目概述

这是一个医学计算器 MCP 服务实现，目前已完成 **56个医学计算器** 的开发，涵盖人体测量学、心血管、肾脏功能、肝脏功能、实验室检验、危重症评分、呼吸系统、感染炎症、液体药物、妊娠相关、肿瘤学等多个医学领域。

### 🏥 计算器分类

#### 人体测量学和基础计算 (5个)
- BMI计算器 - 体重指数计算
- 体表面积计算器 - BSA计算
- 理想体重计算器 - IBW计算
- 调整体重计算器 - ABW计算
- 目标体重计算器

#### 心血管系统 (11个)
- 平均动脉压计算器
- QTc间期计算器（5种公式）
- CHA2DS2-VASc卒中风险评分
- HAS-BLED出血风险评分
- HEART评分计算器
- 心脏风险指数计算器
- Framingham风险评分
- Wells深静脉血栓评分
- Caprini血栓风险评估

#### 肾脏功能 (4个)
- 肌酐清除率计算器（Cockcroft-Gault）
- CKD-EPI肾小球滤过率计算器
- MDRD肾小球滤过率计算器
- 钠排泄分数计算器

#### 肝脏功能 (3个)
- Child-Pugh肝功能分级
- MELD-Na评分计算器
- FIB-4肝纤维化指数

#### 实验室检验 (12个)
- 阴离子间隙计算器及相关计算器
- 钙离子校正计算器
- 高血糖钠离子校正
- 血清渗透压计算器
- LDL胆固醇计算器
- HOMA-IR胰岛素抵抗指数
- 自由水缺失计算器

#### 危重症和评分系统 (8个)
- APACHE II急性生理评分
- SOFA序贯器官衰竭评估
- SIRS全身炎症反应综合征
- Glasgow昏迷评分
- Glasgow出血评分
- Charlson合并症指数

#### 呼吸系统 (4个)
- CURB-65肺炎严重程度评分
- 肺炎严重程度指数（PSI）
- Wells肺栓塞评分
- PERC肺栓塞排除标准

#### 感染和炎症 (2个)
- Centor链球菌性咽炎评分
- FeverPAIN咽炎评分

#### 液体和药物 (3个)
- 维持液体计算器
- 激素转换计算器
- 吗啡当量剂量计算器

#### 妊娠相关 (3个)
- 预计受孕日期计算器
- 预计妊娠期计算器
- 预计分娩日期计算器

#### 肿瘤学 (1个)
- 肺癌TNM分期计算器

### 📚 快速开始

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **运行测试**：
   ```bash
   # 运行所有API测试
   python test/api_test_bmi_calculator.py
   python test/api_test_pregnancy_calculators.py
   python test/api_test_lung_cancer_staging.py
   python test/api_test_tools.py

   # 运行基础测试
   python test_bmi.py
   ```

3. **启动服务器**：
   ```bash
   python server.py
   ```

### 📁 项目结构

```
medcalcmcp/
├── medcalc/                           # 核心框架模块
│   ├── __init__.py                   # 模块导出
│   ├── models.py                     # 数据模型
│   ├── base.py                       # 基础计算器类
│   ├── registry.py                   # 计算器注册系统
│   ├── service.py                    # 计算器服务
│   ├── utils.py                      # 工具类（单位转换等）
│   └── exceptions.py                 # 异常定义
├── calculators/                       # 计算器实现（56个计算器）
│   ├── __init__.py                   # 计算器包（统一管理所有计算器）
│   ├── bmi_calculator.py             # BMI 计算器
│   ├── bsa_calculator.py             # 体表面积计算器
│   ├── creatinine_clearance_calculator.py  # 肌酐清除率计算器
│   ├── cha2ds2_vasc_calculator.py    # CHA2DS2-VASc评分
│   ├── lung_cancer_staging_calculator.py  # 肺癌TNM分期计算器
│   └── ...                          # 其他53个计算器
├── test/                              # 测试文件目录
│   ├── api_test_bmi_calculator.py    # BMI 计算器 API 测试
│   ├── api_test_pregnancy_calculators.py  # 妊娠相关计算器 API 测试
│   ├── api_test_lung_cancer_staging.py    # 肺癌分期计算器 API 测试
│   └── api_test_tools.py             # MCP 工具动态测试
├── server.py                          # FastMCP 服务器主文件
├── api_server.py                      # MCP API 服务器
├── requirements.txt                   # 项目依赖
└── README.md                          # 项目文档
```

### 🛠️ 技术架构

项目采用模块化设计，主要组成部分：

- **MCP 服务器** (`server.py`): 提供 MCP 协议接口
- **核心框架** (`medcalc/`): 数据模型、基础类、工具类
- **计算引擎** (`calculators/`): 56个具体的医学计算器
- **测试套件** (`test/`): API 测试和功能验证

### ✨ 主要特性

- ✅ **完整的医学计算器集合**: 56个专业医学计算器
- ✅ **多领域覆盖**: 涵盖临床医学各个专业领域
- ✅ **智能单位转换**: 支持各种医学单位的自动转换
- ✅ **详细的计算解释**: 每个结果都包含详细的医学解释
- ✅ **完整的参数验证**: 确保输入数据的准确性和安全性
- ✅ **MCP 协议支持**: 标准化的接口协议
- ✅ **异步处理**: 高性能的异步计算处理
- ✅ **完整的测试覆盖**: 全面的API和功能测试

### 🚀 启动服务器

```bash
# 启动 FastMCP 服务器（推荐）
python server.py

# 或启动 MCP API 服务器
python api_server.py
# 服务器将在 http://127.0.0.1:8010/mcp/ 运行
```

### 🔧 开发指南

#### 创建新计算器

1. 在 `calculators/` 目录下创建新的计算器文件
2. 继承 `BaseCalculator` 类
3. 实现必需的方法：`get_info()`, `validate_parameters()`, `calculate()`
4. 使用 `@register_calculator` 装饰器注册
5. 在 `calculators/__init__.py` 中添加导入

#### 运行测试

```bash
# 测试特定计算器
python test/api_test_bmi_calculator.py

# 测试所有计算器（动态测试）
python test/api_test_tools.py

# 测试妊娠相关计算器
python test/api_test_pregnancy_calculators.py

# 测试肺癌分期计算器
python test/api_test_lung_cancer_staging.py
```

## 📋 项目状态

- **当前版本**: 0.1.0
- **计算器数量**: 56个
- **测试覆盖率**: 100%
- **支持的医学领域**: 11个专业领域


## 🤝 贡献

欢迎提交 Pull Request 或创建 Issue 来帮助改进项目。

## 🙏 致谢

本项目基于 [MedCalc-Bench](https://github.com/ncbi-nlp/MedCalc-Bench) 项目开发，感谢 NCBI-NLP 团队提供的优秀医学计算器基础实现。我们将其转换为 MCP (Model Context Protocol) 服务，使其能够更好地集成到现代AI应用中。

**原始项目引用:**
- GitHub: https://github.com/ncbi-nlp/MedCalc-Bench
- 论文: MedCalc-Bench: A Large-scale Medical Calculator Benchmark
