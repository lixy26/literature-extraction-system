# 肝癌文献基因信息提取系统

## 项目简介

本系统基于大语言模型，能够批量读取PDF格式的肝癌相关文献，智能解析文献内容，并按照指定维度提取基因信息，输出结构化的JSON文件。

## 功能特性

- 批量读取PDF文献，支持并发处理
- 集成阿里云百炼大语言模型API
- 针对肝癌细胞相关基因进行结构化信息提取
- 支持多种信息维度提取：表达与预后、靶向治疗、突变与表观遗传、基因基本信息、核心生物学功能、**信号通路与实验模型**
- 输出符合规范的JSON格式文件
- 包含错误处理和重试机制
- **零幻觉约束：严格限制模型只输出文献原文中存在的信息**

## 目录结构

```
literature_extraction_system/
├── __init__.py          # 模块初始化
├── config.py            # 配置文件
├── pdf_reader.py        # PDF文件读取模块
├── prompts.py           # 提示词定义
├── llm_client.py        # LLM客户端
├── processor.py         # 核心处理器
├── utils.py             # 工具函数
├── main.py              # 主入口
├── pdfs/                # PDF文献目录
└── output/              # 输出结果目录
```

## 安装依赖

```bash
pip install pdfplumber requests
```

## 配置说明

1. 在 `config.py` 中配置API密钥：
   ```python
   API_KEY = "your-api-key-here"  # 替换为你的百炼API Key
   ```

2. 将PDF文献放入 `pdfs/` 目录

## 使用方法

系统分两步运行：

**第一步：逐篇提取**
    ```
    python main.py
    ```

逐篇读取 `pdfs/` 目录中的PDF文献，调用大语言模型提取基因信息，将每篇文献的结果单独保存为 `output/pdf_results/*_result.json`。

**第二步：整合汇总**
```
python json_to_sql.py
```

读取第一步生成的所有单篇JSON结果，按基因名称聚合来自不同文献的信息，写入SQLite数据库（`output/gene_info.sqlite3`），并导出最终汇总文件 `output/integrated_gene_results.json`。同一基因在多篇文献中的数据会自动合并，来源文献信息一并保留。

## API密钥获取

访问 [阿里云百炼平台](https://dashscope.aliyuncs.com/) 获取API密钥。

## 输出格式

**单篇文献输出（`output/pdf_results/*_result.json`）**
由 `main.py` 生成，每篇PDF对应一个文件，记录该文献中提取到的所有基因信息：

```json
{
    "metadata": {
        "total_genes": 10,
        "total_pdfs_processed": 5,
        "processing_date": "2026-05-27"
    },
    "genes": {
        "GENE_NAME": {
            "gene_name": "HGNC官方标准基因名称（如 TP53）",
            "basic_info": {
                "gene_function_category": "原癌基因/抑癌基因/双向功能基因/功能未明确"
            },
            "expression_and_prognosis": {
                "expression_level": "高表达/低表达/无显著差异/未提及",
                "prognosis_correlation": {
                    "OS": "正相关/负相关/无关联/未提及",
                    "DFS": "正相关/负相关/无关联/未提及"
                },
                "clinicopathological_correlation": "描述文本或未提及"
            },
            "targeted_therapy": {
                "is_potential_target": "是/否/正在研究/未提及",
                "known_drugs": ["药物名称1", "药物名称2"],
                "drug_resistance": "耐药描述或未提及"
            },
            "mutation_and_epigenetics": {
                "mutation_types": ["点突变", "扩增", "缺失", "甲基化"],
                "mutation_frequency": "具体频率数据或rs号（如 rs1682111），若无则为未提及"
            },
            "biological_functions": ["细胞增殖", "凋亡", "侵袭转移"],
            "mechanisms_and_models": {
                "signaling_pathways": ["通路名称1", "通路名称2"],
                "cancer_subtype": ["HBV相关", "HCV相关"],
                "experimental_model": ["细胞系", "动物模型", "临床标本"],
                "evidence_level": ["临床研究", "动物实验", "细胞实验", "综述"]
            },
            "reference": {
                "title": "参考文献名称",
                "year": "年份",
                "location": "Fig.1C-D, p.4"
            }
        }
    }
}
```
# 整合汇总输出（`output/integrated_gene_results.json`）

由 `json_to_sql.py` 生成，将所有单篇结果按基因名称聚合，同一基因在不同文献中的数据合并为一条记录，并附带来源追溯：

  ```
  {
        "metadata": {
            "total_genes": 25,
            "export_time": "2026-05-27T14:30:00",
            "database_path": "output/gene_info.sqlite3"
        },
        "genes": {
            "GENE_NAME": {
                "gene_name": "TP53",
                "gene_function_category": "抑癌基因",
                "sources": [
                    {"pdf_file": "paper_A.pdf", "pdf_path": "pdfs/paper_A.pdf"},
                    {"pdf_file": "paper_B.pdf", "pdf_path": "pdfs/paper_B.pdf"}
                ],
                "expression_and_prognosis": {
                    "expression_level": "低表达; 高表达",
                    "prognosis_correlation": {
                        "OS": "负相关",
                        "DFS": "未提及"
                    },
                    "clinicopathological_correlation": "与TNM分期相关 (paper_A.pdf)"
                },
                "targeted_therapy": {
                    "is_potential_target": "是",
                    "known_drugs": "药物A; 药物B",
                    "drug_resistance": "未提及"
                },
                "mutation_and_epigenetics": {
                    "mutation_types": "点突变; 甲基化",
                    "mutation_frequency": "32% (paper_A.pdf)"
                },
                "biological_functions": [
                    "细胞增殖 (来源: paper_A.pdf, paper_B.pdf)",
                    "凋亡 (来源: paper_A.pdf)"
                ],
                "mechanisms_and_models": {
                    "signaling_pathways": ["PI3K/AKT", "Wnt"],
                    "cancer_subtype": ["HBV相关"],
                    "experimental_model": ["细胞系", "动物模型"],
                    "evidence_level": ["临床研究", "细胞实验"]
                },
                "references": [
                    {
                        "title": "参考文献标题",
                        "year": "2024",
                        "location": "Fig.2A, p.6",
                        "source_pdf": "paper_A.pdf"
                    }
                ]
            }
        }
    }
```

同时生成 SQLite 数据库 `output/gene_info.sqlite3`，包含 `documents`、`genes`、`expression_prognosis`、`targeted_therapy`、`mutation_epigenetics`、`biological_functions`、`mechanisms_and_models`、`gene_references` 共8张表，支持自定义查询与后续分析。
## 提取维度说明

### A. 表达与预后信息
- 肝癌组织表达水平：高表达 / 低表达 / 无显著差异 / 未提及
- 预后相关性：与总生存期（OS）和无病生存期（DFS）的相关性
- 临床病理特征关联：肿瘤大小、TNM分期、分化程度、血管侵犯

### B. 靶向与治疗信息
- 是否为潜在治疗靶点：是 / 否 / 正在研究 / 未提及
- 已知靶向药物（`known_drugs` 字段，列表格式，如无则为空列表 `[]`）
- 耐药相关性描述

### C. 突变与表观遗传信息
- 常见突变类型（`mutation_types` 字段，列表格式）：点突变、扩增、缺失、甲基化等
- 突变频率（`mutation_frequency` 字段，字符串格式）：包含具体数据，或 SNP rs 编号（如 `rs1682111`）

### D. 基因基本信息
- 基因名称：使用 HGNC 官方标准命名（如 TP53，不使用别名）
- 基因功能分类：原癌基因 / 抑癌基因 / 双向功能基因 / 功能未明确

### E. 核心生物学功能
`biological_functions` 字段，列表格式，可选值：细胞增殖、凋亡、侵袭转移、血管生成、代谢重编程、免疫逃逸、耐药

### F. 机制与模型信息（新增）
- **信号通路**（`signaling_pathways`）：如 Wnt、PI3K/AKT、MAPK 等
- **癌症亚型**（`cancer_subtype`）：HBV相关 / HCV相关 / 酒精性 / NASH相关 / 胆管细胞癌
- **实验模型**（`experimental_model`）：细胞系 / 动物模型 / 临床标本
- **证据等级**（`evidence_level`）：临床研究 / 动物实验 / 细胞实验 / 综述

> 以上 F 类字段均为列表格式，若文献中无相关信息则输出空列表 `[]`。

## 字段类型规范

| 字段 | 类型 | 无信息时的占位值 |
|------|------|----------------|
| `known_drugs` | 列表 | `[]` |
| `mutation_types` | 列表 | `[]` |
| `biological_functions` | 列表 | `[]` |
| `signaling_pathways` | 列表 | `[]` |
| `cancer_subtype` | 列表 | `[]` |
| `experimental_model` | 列表 | `[]` |
| `evidence_level` | 列表 | `[]` |
| `expression_level` | 字符串 | `"未提及"` |
| `drug_resistance` | 字符串 | `"未提及"` |
| `mutation_frequency` | 字符串 | `"未提及"` |
| `reference.location` | 字符串 | `"未提及"` |

> **注意**：`reference.location` 必须为字符串，多个位置用逗号连接（如 `"Fig.1C-D, p.4"`），最多保留3处核心证据位置，**禁止输出列表格式**。

## 注意事项

1. 确保API密钥有效且余额充足
2. PDF文件需为可提取文本的格式（非扫描版）
3. 大文件可能需要较长处理时间
4. 建议在网络稳定的环境下运行
5. 系统严格遵守零幻觉原则：所有提取结果均来自文献原文，不会基于模型自身知识进行补充或推测
