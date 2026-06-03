# LLM输出评估系统

本系统用于评估LLM（大语言模型）从PDF文献中提取基因信息的准确性，包含两种评估方式：

1. **人工标注评估** - 对比人工标注与LLM输出，评估信息抽取的准确性
2. **数据库对比** - 对比LLM输出与权威数据库（如KEGG、COSMIC），评估生物学合理性

## 目录结构

```
evaluation/
├── schema.py              # 数据结构定义（与LLM输出一致）
├── annotation_ui.py       # 人工标注Web界面
├── templates/
│   └── index.html         # 标注界面前端
├── evaluate.py            # 人工标注与LLM输出对比脚本
├── database_validation.py # 数据库对比验证脚本
├── databases/             # 权威数据库文件
│   ├── kegg.json          # KEGG通路数据库
│   └── cosmic.json        # COSMIC突变数据库
└── annotations/           # 人工标注文件存储目录
```

## 一、人工标注评估

### 1. 启动标注界面

```bash
cd evaluation
python annotation_ui.py
```

然后访问 http://localhost:5001

### 2. 使用说明

1. 在"新建标注"页面填写基因信息
2. 选择来源PDF文件
3. 填写各项字段（与LLM输出格式一致）
4. 点击"保存标注"生成JSON文件
5. 在"标注历史"页面查看和管理已标注文件

### 3. 运行评估对比

```bash
python evaluate.py --output evaluation_report.json
```

### 评估指标说明

| 指标 | 说明 |
|------|------|
| Precision | 精确率：模型预测正确的比例 |
| Recall | 召回率：模型覆盖的真实信息比例 |
| F1 Score | 综合指标：2 * P * R / (P + R) |
| Hallucination Rate | 幻觉率：预测错误的比例 |

## 二、数据库对比验证

### 1. 创建示例数据库

```bash
python database_validation.py --create-samples
```

### 2. 运行数据库对比

```bash
python database_validation.py --databases kegg cosmic --output validation_report.json
```

### 3. 数据库格式

数据库文件为JSON格式，存放在 `databases/` 目录下：

```json
{
  "基因名称": {
    "pathways": ["通路1", "通路2"],
    "functions": ["功能1", "功能2"],
    "mutation": "true"
  }
}
```

## 三、数据结构

系统使用统一的schema，与LLM输出格式完全一致：

```python
GeneAnnotation {
    gene_name: str                    # 基因名称
    basic_info: {
        gene_function_category: str   # 功能分类
    }
    expression_and_prognosis: {       # 表达与预后
        expression_level: str
        prognosis_os: str
        prognosis_dfs: str
        clinicopathological_correlation: str
        location: str
    }
    targeted_therapy: {               # 靶向治疗
        is_potential_target: str
        known_drugs: List[str]
        drug_resistance: str
    }
    mutation_and_epigenetics: {       # 突变与表观遗传
        mutation_types: List[str]
        mutation_frequency: str
    }
    mechanisms_and_models: {          # 机制与模型
        signaling_pathways: List[str]
        cancer_subtype: List[str]
        experimental_model: List[str]
        evidence_level: List[str]
    }
    biological_functions: List[str]   # 核心生物学功能
    references: List[Reference]       # 参考文献
    sources: List[Dict]               # 来源文件
}
```

## 四、最佳实践

### 人工标注流程

1. **制定标注规范** - 编写Annotation Guideline
2. **双人标注** - 至少2名标注员
3. **一致性评估** - 计算Cohen's Kappa
4. **生成Gold JSON** - 确保格式与LLM输出完全一致
5. **自动对比** - 使用evaluate.py计算指标

### 数据库对比流程

1. **选择对标数据库** - 根据字段选择数据源
2. **统一ID** - 基因名转HGNC，通路名映射到标准ID
3. **构建对齐表** - 创建alias → standard name映射
4. **定义匹配规则** - 支持exact match和alias match
5. **计算指标** - 重点关注Precision和Recall

## 五、输出报告示例

```json
{
  "summary": {
    "llm_output_count": 17,
    "annotation_count": 5,
    "common_gene_count": 3
  },
  "overall_metrics": {
    "precision": 0.85,
    "recall": 0.78,
    "f1": 0.81,
    "hallucination_rate": 0.15
  },
  "field_metrics": {
    "expression_and_prognosis.expression_level": {
      "f1": 0.92,
      "precision": 0.90,
      "recall": 0.94
    }
  }
}
```
