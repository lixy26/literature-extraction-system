#!/usr/bin/env python3
"""
LLM输出评估系统 - Schema定义

定义与LLM输出完全一致的数据结构
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass
class ExpressionAndPrognosis:
    """表达与预后信息"""
    expression_level: str = ""
    prognosis_os: str = ""
    prognosis_dfs: str = ""
    clinicopathological_correlation: str = ""
    location: str = ""


@dataclass
class TargetedTherapy:
    """靶向治疗信息"""
    is_potential_target: str = ""
    known_drugs: List[str] = field(default_factory=list)
    drug_resistance: str = ""


@dataclass
class MutationEpigenetics:
    """突变与表观遗传信息"""
    mutation_types: List[str] = field(default_factory=list)
    mutation_frequency: str = ""


@dataclass
class MechanismsAndModels:
    """机制与模型信息"""
    signaling_pathways: List[str] = field(default_factory=list)
    cancer_subtype: List[str] = field(default_factory=list)
    experimental_model: List[str] = field(default_factory=list)
    evidence_level: List[str] = field(default_factory=list)


@dataclass
class Reference:
    """参考文献信息"""
    title: str = ""
    year: str = ""
    location: str = ""
    source_pdf: str = ""


@dataclass
class GeneAnnotation:
    """基因标注信息"""
    gene_name: str = ""
    basic_info: Dict[str, str] = field(default_factory=dict)
    expression_and_prognosis: ExpressionAndPrognosis = field(default_factory=ExpressionAndPrognosis)
    targeted_therapy: TargetedTherapy = field(default_factory=TargetedTherapy)
    mutation_and_epigenetics: MutationEpigenetics = field(default_factory=MutationEpigenetics)
    mechanisms_and_models: MechanismsAndModels = field(default_factory=MechanismsAndModels)
    biological_functions: List[str] = field(default_factory=list)
    references: List[Reference] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "gene_name": self.gene_name,
            "basic_info": self.basic_info,
            "expression_and_prognosis": {
                "expression_level": self.expression_and_prognosis.expression_level,
                "prognosis_os": self.expression_and_prognosis.prognosis_os,
                "prognosis_dfs": self.expression_and_prognosis.prognosis_dfs,
                "clinicopathological_correlation": self.expression_and_prognosis.clinicopathological_correlation,
                "location": self.expression_and_prognosis.location
            },
            "targeted_therapy": {
                "is_potential_target": self.targeted_therapy.is_potential_target,
                "known_drugs": self.targeted_therapy.known_drugs,
                "drug_resistance": self.targeted_therapy.drug_resistance
            },
            "mutation_and_epigenetics": {
                "mutation_types": self.mutation_and_epigenetics.mutation_types,
                "mutation_frequency": self.mutation_and_epigenetics.mutation_frequency
            },
            "mechanisms_and_models": {
                "signaling_pathways": self.mechanisms_and_models.signaling_pathways,
                "cancer_subtype": self.mechanisms_and_models.cancer_subtype,
                "experimental_model": self.mechanisms_and_models.experimental_model,
                "evidence_level": self.mechanisms_and_models.evidence_level
            },
            "biological_functions": self.biological_functions,
            "references": [{
                "title": ref.title,
                "year": ref.year,
                "location": ref.location,
                "source_pdf": ref.source_pdf
            } for ref in self.references],
            "sources": self.sources
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeneAnnotation':
        """从字典创建对象"""
        expr_prog_data = data.get("expression_and_prognosis", {})
        therapy_data = data.get("targeted_therapy", {})
        mut_data = data.get("mutation_and_epigenetics", {})
        mech_data = data.get("mechanisms_and_models", {})
        
        return cls(
            gene_name=data.get("gene_name", ""),
            basic_info=data.get("basic_info", {}),
            expression_and_prognosis=ExpressionAndPrognosis(
                expression_level=expr_prog_data.get("expression_level", ""),
                prognosis_os=expr_prog_data.get("prognosis_os", ""),
                prognosis_dfs=expr_prog_data.get("prognosis_dfs", ""),
                clinicopathological_correlation=expr_prog_data.get("clinicopathological_correlation", ""),
                location=expr_prog_data.get("location", "")
            ),
            targeted_therapy=TargetedTherapy(
                is_potential_target=therapy_data.get("is_potential_target", ""),
                known_drugs=therapy_data.get("known_drugs", []),
                drug_resistance=therapy_data.get("drug_resistance", "")
            ),
            mutation_and_epigenetics=MutationEpigenetics(
                mutation_types=mut_data.get("mutation_types", []),
                mutation_frequency=mut_data.get("mutation_frequency", "")
            ),
            mechanisms_and_models=MechanismsAndModels(
                signaling_pathways=mech_data.get("signaling_pathways", []),
                cancer_subtype=mech_data.get("cancer_subtype", []),
                experimental_model=mech_data.get("experimental_model", []),
                evidence_level=mech_data.get("evidence_level", [])
            ),
            biological_functions=data.get("biological_functions", []),
            references=[Reference(
                title=ref.get("title", ""),
                year=ref.get("year", ""),
                location=ref.get("location", ""),
                source_pdf=ref.get("source_pdf", "")
            ) for ref in data.get("references", [])],
            sources=data.get("sources", [])
        )

    def save_to_json(self, filepath: Path):
        """保存为JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


def load_annotation_from_json(filepath: Path) -> GeneAnnotation:
    """从JSON文件加载标注"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return GeneAnnotation.from_dict(data)


# 字段定义常量
FIELD_DEFINITIONS = {
    "expression_level": {
        "label": "表达水平",
        "description": "基因在肝癌组织中的表达水平",
        "options": ["高表达", "低表达", "未提及"]
    },
    "prognosis_os": {
        "label": "总生存期(OS)",
        "description": "与总生存期的相关性",
        "options": ["正相关", "负相关", "未提及"]
    },
    "prognosis_dfs": {
        "label": "无病生存期(DFS)",
        "description": "与无病生存期的相关性",
        "options": ["正相关", "负相关", "未提及"]
    },
    "is_potential_target": {
        "label": "潜在靶点",
        "description": "是否为潜在的药物靶点",
        "options": ["是", "否", "正在研究", "未提及"]
    },
    "gene_function_category": {
        "label": "基因功能分类",
        "description": "基因的功能类别",
        "options": ["原癌基因", "抑癌基因", "双向功能基因", "功能未明确"]
    }
}
