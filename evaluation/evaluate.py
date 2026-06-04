#!/usr/bin/env python3
"""
LLM输出评估系统 - 评估对比脚本

用于对比人工标注与LLM输出，计算各项指标
支持按PDF文件匹配进行比对
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from schema import GeneAnnotation, load_annotation_from_json
import argparse


class Evaluator:
    """评估器类"""
    
    def __init__(self):
        self.llm_output_dir = Path(__file__).parent.parent / "output" / "pdf_results"
        self.annotation_dir = Path(__file__).parent / "annotations"
    
    def load_llm_outputs_by_pdf(self) -> Dict[str, Dict[str, Any]]:
        """加载所有LLM输出，按PDF文件分组
        
        返回格式: {
            "main.pdf": {
                "genes": {"基因名": {...}}
            }
        }
        """
        llm_outputs = {}
        if self.llm_output_dir.exists():
            for json_file in self.llm_output_dir.glob("*_result.json"):
                try:
                    # 从文件名提取PDF名称
                    # 格式: xxx_result.json -> xxx.pdf
                    pdf_name = json_file.stem.replace("_result", "") + ".pdf"
                    
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    genes = {}
                    for gene in data.get("genes", []):
                        gene_name = gene.get("gene_name", "")
                        if gene_name:
                            genes[gene_name] = gene
                    
                    llm_outputs[pdf_name] = {
                        "pdf_file": pdf_name,
                        "genes": genes
                    }
                except Exception as e:
                    print(f"加载LLM输出失败 {json_file}: {e}")
        return llm_outputs
    
    def load_annotations_by_pdf(self) -> Dict[str, Dict[str, GeneAnnotation]]:
        """加载所有人工标注，按PDF文件分组
        对于同一篇PDF的同一基因，只保留时间最新的标注
        支持新旧两种标注格式
        
        返回格式: {
            "main.pdf": {
                "genes": {"基因名": GeneAnnotation对象}
            }
        }
        """
        # 临时存储：(pdf_name, gene_name) -> (annotation, file_mtime)
        temp_storage = {}
        
        if self.annotation_dir.exists():
            for ann_file in self.annotation_dir.glob("*_annotation.json"):
                try:
                    with open(ann_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    file_mtime = ann_file.stat().st_mtime
                    
                    # 判断是哪种格式
                    # 新格式：有顶层pdf_file和genes数组
                    if "pdf_file" in data and "genes" in data:
                        pdf_name = data.get("pdf_file", "")
                        if not pdf_name:
                            print(f"警告: 标注文件 {ann_file} 未指定源PDF")
                            continue
                        
                        for gene_data in data.get("genes", []):
                            ann = GeneAnnotation.from_dict(gene_data)
                            if ann.gene_name:
                                key = (pdf_name, ann.gene_name)
                                if key not in temp_storage or file_mtime > temp_storage[key][1]:
                                    temp_storage[key] = (ann, file_mtime)
                    
                    # 旧格式：单基因标注，有sources或references
                    else:
                        ann = GeneAnnotation.from_dict(data)
                        
                        # 获取源PDF文件
                        pdf_name = ""
                        if ann.sources:
                            pdf_name = ann.sources[0].get("pdf_file", "") if ann.sources else ""
                        if not pdf_name and ann.references:
                            pdf_name = ann.references[0].source_pdf if ann.references else ""
                        if not pdf_name and hasattr(ann, 'pdf_file'):
                            pdf_name = ann.pdf_file
                        
                        if not pdf_name:
                            print(f"警告: 标注文件 {ann_file} 未指定源PDF")
                            continue
                        
                        if ann.gene_name:
                            key = (pdf_name, ann.gene_name)
                            if key not in temp_storage or file_mtime > temp_storage[key][1]:
                                temp_storage[key] = (ann, file_mtime)
                                
                except Exception as e:
                    print(f"加载标注失败 {ann_file}: {e}")
        
        # 转换为返回格式
        annotations = {}
        for (pdf_name, gene_name), (ann, _) in temp_storage.items():
            if pdf_name not in annotations:
                annotations[pdf_name] = {"pdf_file": pdf_name, "genes": {}}
            annotations[pdf_name]["genes"][gene_name] = ann
        
        return annotations
    
    def compare_strings(self, pred: str, gold: str) -> Tuple[int, int, int]:
        """比较两个字符串字段"""
        pred_norm = pred.strip() if pred else ""
        gold_norm = gold.strip() if gold else ""
        
        # 处理"未提及"情况
        if gold_norm == "" or gold_norm == "未提及":
            if pred_norm == "" or pred_norm == "未提及":
                return (1, 0, 0)  # TN - 都未提及
            else:
                return (0, 1, 0)  # FP - 预测有但实际无
        
        if pred_norm == "" or pred_norm == "未提及":
            return (0, 0, 1)  # FN - 预测无但实际有
        
        if pred_norm == gold_norm:
            return (1, 0, 0)  # TP
        else:
            return (0, 1, 1)  # 都有但不一致
    
    def compare_lists(self, pred: List[str], gold: List[str]) -> Tuple[int, int, int]:
        """比较两个列表字段（集合匹配）"""
        pred_set = set([p.strip() for p in pred if p.strip() and p.strip() != "未提及"])
        gold_set = set([g.strip() for g in gold if g.strip() and g.strip() != "未提及"])
        
        if len(gold_set) == 0:
            if len(pred_set) == 0:
                return (1, 0, 0)  # TN
            else:
                return (0, len(pred_set), 0)  # FP
        
        if len(pred_set) == 0:
            return (0, 0, len(gold_set))  # FN
        
        tp = len(pred_set & gold_set)
        fp = len(pred_set - gold_set)
        fn = len(gold_set - pred_set)
        
        return (tp, fp, fn)
    
    def evaluate_gene(self, pred: Dict[str, Any], gold: GeneAnnotation) -> Dict[str, Any]:
        """评估单个基因"""
        results = {}
        
        # 基本信息
        results["basic_info"] = {}
        results["basic_info"]["gene_function_category"] = self.compare_strings(
            pred.get("basic_info", {}).get("gene_function_category", ""),
            gold.basic_info.get("gene_function_category", "")
        )
        
        # 表达与预后
        results["expression_and_prognosis"] = {}
        exp_prog = pred.get("expression_and_prognosis", {})
        results["expression_and_prognosis"]["expression_level"] = self.compare_strings(
            exp_prog.get("expression_level", ""),
            gold.expression_and_prognosis.expression_level
        )
        results["expression_and_prognosis"]["prognosis_os"] = self.compare_strings(
            exp_prog.get("prognosis_os", "") or exp_prog.get("prognosis_correlation", {}).get("OS", ""),
            gold.expression_and_prognosis.prognosis_os
        )
        results["expression_and_prognosis"]["prognosis_dfs"] = self.compare_strings(
            exp_prog.get("prognosis_dfs", "") or exp_prog.get("prognosis_correlation", {}).get("DFS", ""),
            gold.expression_and_prognosis.prognosis_dfs
        )
        results["expression_and_prognosis"]["clinicopathological_correlation"] = self.compare_strings(
            exp_prog.get("clinicopathological_correlation", ""),
            gold.expression_and_prognosis.clinicopathological_correlation
        )
        
        # 靶向治疗
        results["targeted_therapy"] = {}
        therapy = pred.get("targeted_therapy", {})
        results["targeted_therapy"]["is_potential_target"] = self.compare_strings(
            therapy.get("is_potential_target", ""),
            gold.targeted_therapy.is_potential_target
        )
        results["targeted_therapy"]["known_drugs"] = self.compare_lists(
            therapy.get("known_drugs", []),
            gold.targeted_therapy.known_drugs
        )
        results["targeted_therapy"]["drug_resistance"] = self.compare_strings(
            therapy.get("drug_resistance", ""),
            gold.targeted_therapy.drug_resistance
        )
        
        # 突变与表观遗传
        results["mutation_and_epigenetics"] = {}
        mut = pred.get("mutation_and_epigenetics", {})
        results["mutation_and_epigenetics"]["mutation_types"] = self.compare_lists(
            mut.get("mutation_types", []),
            gold.mutation_and_epigenetics.mutation_types
        )
        results["mutation_and_epigenetics"]["mutation_frequency"] = self.compare_strings(
            mut.get("mutation_frequency", ""),
            gold.mutation_and_epigenetics.mutation_frequency
        )
        
        # 机制与模型
        results["mechanisms_and_models"] = {}
        mech = pred.get("mechanisms_and_models", {})
        results["mechanisms_and_models"]["signaling_pathways"] = self.compare_lists(
            mech.get("signaling_pathways", []),
            gold.mechanisms_and_models.signaling_pathways
        )
        results["mechanisms_and_models"]["cancer_subtype"] = self.compare_lists(
            mech.get("cancer_subtype", []),
            gold.mechanisms_and_models.cancer_subtype
        )
        results["mechanisms_and_models"]["experimental_model"] = self.compare_lists(
            mech.get("experimental_model", []),
            gold.mechanisms_and_models.experimental_model
        )
        
        # 生物学功能
        results["biological_functions"] = self.compare_lists(
            pred.get("biological_functions", []),
            gold.biological_functions
        )
        
        return results
    
    def compute_metrics(self, results: Dict[str, Any]) -> Dict[str, float]:
        """计算整体指标"""
        total_tp = 0
        total_fp = 0
        total_fn = 0
        
        def sum_metrics(obj):
            nonlocal total_tp, total_fp, total_fn
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, tuple) and len(value) == 3:
                        total_tp += value[0]
                        total_fp += value[1]
                        total_fn += value[2]
                    else:
                        sum_metrics(value)
        
        sum_metrics(results)
        
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        hallucination_rate = total_fp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "hallucination_rate": round(hallucination_rate, 4),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn
        }
    
    def evaluate(self) -> Dict[str, Any]:
        """执行评估（按PDF文件匹配）"""
        # 加载数据
        llm_outputs = self.load_llm_outputs_by_pdf()
        annotations = self.load_annotations_by_pdf()
        
        report = {
            "summary": {
                "llm_pdf_count": len(llm_outputs),
                "annotation_pdf_count": len(annotations),
                "matched_pdf_count": 0
            },
            "pdf_reports": {},
            "overall_metrics": {}
        }
        
        # 按PDF文件匹配
        total_tp = 0
        total_fp = 0
        total_fn = 0
        
        for pdf_name, llm_data in llm_outputs.items():
            if pdf_name not in annotations:
                print(f"警告: PDF {pdf_name} 没有对应的人工标注")
                continue
            
            report["summary"]["matched_pdf_count"] += 1
            
            # 获取该PDF的LLM输出和标注
            llm_genes = llm_data["genes"]
            gold_genes = annotations[pdf_name]["genes"]
            
            pdf_report = {
                "pdf_file": pdf_name,
                "llm_gene_count": len(llm_genes),
                "annotation_gene_count": len(gold_genes),
                "common_genes": [],
                "llm_only_genes": [],
                "annotation_only_genes": [],
                "gene_results": {},
                "metrics": {}
            }
            
            # 找出共同基因
            common_gene_names = set(llm_genes.keys()) & set(gold_genes.keys())
            pdf_report["common_genes"] = list(common_gene_names)
            pdf_report["llm_only_genes"] = list(set(llm_genes.keys()) - common_gene_names)
            pdf_report["annotation_only_genes"] = list(set(gold_genes.keys()) - common_gene_names)
            
            # 评估每个共同基因
            gene_results = {}
            for gene_name in common_gene_names:
                gene_results[gene_name] = self.evaluate_gene(llm_genes[gene_name], gold_genes[gene_name])
            
            pdf_report["gene_results"] = gene_results
            
            # 计算该PDF的指标
            pdf_metrics = self.compute_metrics(gene_results)
            pdf_report["metrics"] = pdf_metrics
            
            # 累加到总体
            total_tp += pdf_metrics["total_tp"]
            total_fp += pdf_metrics["total_fp"]
            total_fn += pdf_metrics["total_fn"]
            
            report["pdf_reports"][pdf_name] = pdf_report
        
        # 计算总体指标
        if (total_tp + total_fp) > 0:
            overall_precision = total_tp / (total_tp + total_fp)
            overall_hallucination = total_fp / (total_tp + total_fp)
        else:
            overall_precision = 0
            overall_hallucination = 0
        
        if (total_tp + total_fn) > 0:
            overall_recall = total_tp / (total_tp + total_fn)
        else:
            overall_recall = 0
        
        if (overall_precision + overall_recall) > 0:
            overall_f1 = 2 * overall_precision * overall_recall / (overall_precision + overall_recall)
        else:
            overall_f1 = 0
        
        report["overall_metrics"] = {
            "precision": round(overall_precision, 4),
            "recall": round(overall_recall, 4),
            "f1": round(overall_f1, 4),
            "hallucination_rate": round(overall_hallucination, 4),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn
        }
        
        return report


def main():
    parser = argparse.ArgumentParser(description="LLM输出评估工具")
    parser.add_argument("--output", default="evaluation/evaluation_report.json", help="输出报告文件名")
    args = parser.parse_args()
    
    evaluator = Evaluator()
    report = evaluator.evaluate()
    
    # 打印摘要
    print(f"=== 评估摘要 ===")
    print(f"LLM输出PDF数量: {report['summary']['llm_pdf_count']}")
    print(f"人工标注PDF数量: {report['summary']['annotation_pdf_count']}")
    print(f"匹配的PDF数量: {report['summary']['matched_pdf_count']}")
    print(f"\n=== 总体指标 ===")
    print(f"Precision: {report['overall_metrics']['precision']}")
    print(f"Recall: {report['overall_metrics']['recall']}")
    print(f"F1 Score: {report['overall_metrics']['f1']}")
    print(f"Hallucination Rate: {report['overall_metrics']['hallucination_rate']}")
    
    # 保存报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n报告已保存到: {output_path.resolve()}")


if __name__ == "__main__":
    main()
