#!/usr/bin/env python3
"""
LLM输出评估系统 - 数据库对比模块

用于对比LLM输出与权威数据库（如KEGG、COSMIC、TCGA等）
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Set
import argparse


class DatabaseValidator:
    """数据库验证器"""
    
    def __init__(self):
        self.llm_output_dir = Path(__file__).parent.parent / "output" / "pdf_results"
        self.database_dir = Path(__file__).parent / "databases"
        
        # 创建数据库目录
        self.database_dir.mkdir(exist_ok=True)
        
        # 预定义的通路别名映射
        self.pathway_aliases = {
            "PI3K/AKT": ["PI3K/AKT", "PI3K-Akt", "PI3K-AKT", "PI3K/Akt pathway", "AKT pathway"],
            "Wnt": ["Wnt", "WNT", "Wnt signaling", "WNT pathway"],
            "MAPK": ["MAPK", "MAP kinase", "MAPK pathway"],
            "Notch": ["Notch", "Notch signaling"],
            "Hippo": ["Hippo", "Hippo pathway"],
            "TGF-beta": ["TGF-beta", "TGFβ", "TGF-beta pathway"],
            "NF-kB": ["NF-kB", "NF-κB", "NFkB", "NF-kappaB"],
            "JAK-STAT": ["JAK-STAT", "JAK/STAT", "JAK STAT"],
            "mTOR": ["mTOR", "mTOR pathway", "mTORC1"],
            "RAS": ["RAS", "Ras", "RAS pathway"]
        }
        
        # 预定义的基因功能别名
        self.function_aliases = {
            "细胞增殖": ["细胞增殖", "增殖", "proliferation"],
            "细胞凋亡": ["细胞凋亡", "凋亡", "apoptosis"],
            "侵袭转移": ["侵袭转移", "转移", "侵袭", "metastasis", "invasion"],
            "代谢重编程": ["代谢重编程", "代谢", "metabolism", "glycolysis"],
            "免疫逃逸": ["免疫逃逸", "免疫", "immune"],
            "血管生成": ["血管生成", "angiogenesis"],
            "细胞周期": ["细胞周期", "cell cycle"]
        }
    
    def load_llm_outputs(self) -> Dict[str, Any]:
        """加载所有LLM输出"""
        llm_outputs = {}
        if self.llm_output_dir.exists():
            for json_file in self.llm_output_dir.glob("*_result.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for gene in data.get("genes", []):
                            gene_name = gene.get("gene_name", "")
                            if gene_name:
                                llm_outputs[gene_name] = gene
                except Exception as e:
                    print(f"加载LLM输出失败 {json_file}: {e}")
        return llm_outputs
    
    def load_database(self, db_name: str) -> Dict[str, Any]:
        """加载指定数据库"""
        db_file = self.database_dir / f"{db_name}.json"
        if db_file.exists():
            with open(db_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_database(self, db_name: str, data: Dict[str, Any]):
        """保存数据库"""
        db_file = self.database_dir / f"{db_name}.json"
        with open(db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def normalize_pathway(self, pathway: str) -> str:
        """标准化通路名称"""
        pathway = pathway.strip().lower()
        for standard, aliases in self.pathway_aliases.items():
            if any(alias.lower() in pathway for alias in aliases):
                return standard
        return pathway
    
    def normalize_function(self, func: str) -> str:
        """标准化功能名称"""
        func = func.strip().lower()
        for standard, aliases in self.function_aliases.items():
            if any(alias.lower() in func for alias in aliases):
                return standard
        return func
    
    def match_pathway(self, pred_pathway: str, gold_pathways: List[str]) -> bool:
        """检查通路是否匹配"""
        pred_norm = self.normalize_pathway(pred_pathway)
        
        for gold_pathway in gold_pathways:
            gold_norm = self.normalize_pathway(gold_pathway)
            if pred_norm == gold_norm or pred_norm in gold_norm or gold_norm in pred_norm:
                return True
        return False
    
    def evaluate_against_database(self, llm_outputs: Dict[str, Any], database: Dict[str, Any], 
                                  db_name: str) -> Dict[str, Any]:
        """评估LLM输出与指定数据库的一致性"""
        results = {}
        
        for gene_name, gene_data in llm_outputs.items():
            if gene_name not in database:
                continue
            
            gene_results = {}
            db_entry = database[gene_name]
            
            # 评估通路
            llm_pathways = gene_data.get("mechanisms_and_models", {}).get("signaling_pathways", [])
            db_pathways = db_entry.get("pathways", [])
            
            tp = 0
            fp = 0
            fn = 0
            
            for pathway in llm_pathways:
                if self.match_pathway(pathway, db_pathways):
                    tp += 1
                else:
                    fp += 1
            
            for pathway in db_pathways:
                found = False
                for llm_pathway in llm_pathways:
                    if self.match_pathway(llm_pathway, [pathway]):
                        found = True
                        break
                if not found:
                    fn += 1
            
            gene_results["pathways"] = {
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "predicted": llm_pathways,
                "database": db_pathways,
                "matched": [p for p in llm_pathways if self.match_pathway(p, db_pathways)]
            }
            
            # 评估基因功能
            llm_functions = gene_data.get("biological_functions", [])
            db_functions = db_entry.get("functions", [])
            
            func_tp = 0
            func_fp = 0
            func_fn = 0
            
            for func in llm_functions:
                norm_func = self.normalize_function(func)
                if any(self.normalize_function(f) == norm_func for f in db_functions):
                    func_tp += 1
                else:
                    func_fp += 1
            
            for func in db_functions:
                norm_func = self.normalize_function(func)
                found = False
                for llm_func in llm_functions:
                    if self.normalize_function(llm_func) == norm_func:
                        found = True
                        break
                if not found:
                    func_fn += 1
            
            gene_results["functions"] = {
                "tp": func_tp,
                "fp": func_fp,
                "fn": func_fn,
                "predicted": llm_functions,
                "database": db_functions
            }
            
            # 评估突变状态
            llm_mutation = gene_data.get("mutation_and_epigenetics", {}).get("mutation_types", [])
            db_mutation = db_entry.get("mutation", "")
            
            if db_mutation:
                has_mutation = len(llm_mutation) > 0 and any(m not in ["未提及", ""] for m in llm_mutation)
                gene_results["mutation"] = {
                    "match": has_mutation == (db_mutation == "true" or db_mutation is True),
                    "predicted": llm_mutation,
                    "database": db_mutation
                }
            
            results[gene_name] = gene_results
        
        return results
    
    def compute_database_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """计算数据库对比指标"""
        total_tp = 0
        total_fp = 0
        total_fn = 0
        
        for gene_name, gene_results in results.items():
            if "pathways" in gene_results:
                total_tp += gene_results["pathways"]["tp"]
                total_fp += gene_results["pathways"]["fp"]
                total_fn += gene_results["pathways"]["fn"]
            
            if "functions" in gene_results:
                total_tp += gene_results["functions"]["tp"]
                total_fp += gene_results["functions"]["fp"]
                total_fn += gene_results["functions"]["fn"]
        
        precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "total_tp": total_tp,
            "total_fp": total_fp,
            "total_fn": total_fn
        }
    
    def run_database_validation(self, db_names: List[str] = None) -> Dict[str, Any]:
        """运行数据库验证"""
        if db_names is None:
            db_names = ["kegg", "cosmic"]
        
        llm_outputs = self.load_llm_outputs()
        print(f"加载了 {len(llm_outputs)} 个LLM输出基因")
        
        validation_results = {}
        
        for db_name in db_names:
            database = self.load_database(db_name)
            print(f"\n正在对比数据库: {db_name}")
            print(f"数据库包含 {len(database)} 个基因")
            
            if len(database) == 0:
                print(f"警告: 数据库 {db_name} 为空，请先导入数据")
                continue
            
            results = self.evaluate_against_database(llm_outputs, database, db_name)
            metrics = self.compute_database_metrics(results)
            
            validation_results[db_name] = {
                "summary": {
                    "llm_gene_count": len(llm_outputs),
                    "db_gene_count": len(database),
                    "matched_gene_count": len(results)
                },
                "metrics": metrics,
                "detailed_results": results
            }
            
            print(f"匹配基因数: {len(results)}")
            print(f"Precision: {metrics['precision']}")
            print(f"Recall: {metrics['recall']}")
            print(f"F1: {metrics['f1']}")
        
        return validation_results


def create_sample_databases():
    """创建示例数据库文件"""
    db_dir = Path(__file__).parent / "databases"
    db_dir.mkdir(exist_ok=True)
    
    # KEGG通路数据库示例
    kegg_data = {
        "PTEN": {
            "pathways": ["PI3K-Akt signaling pathway", "FoxO signaling pathway", "mTOR signaling pathway"],
            "functions": ["细胞增殖", "凋亡", "代谢重编程"]
        },
        "TP53": {
            "pathways": ["p53 signaling pathway", "Cell cycle", "Apoptosis"],
            "functions": ["细胞周期调控", "凋亡", "DNA修复"]
        },
        "CTNNB1": {
            "pathways": ["Wnt signaling pathway", "Hippo signaling pathway"],
            "functions": ["细胞增殖", "侵袭转移"]
        },
        "MYC": {
            "pathways": ["Cell cycle", "MAPK signaling pathway"],
            "functions": ["细胞增殖", "细胞周期"]
        },
        "NRAS": {
            "pathways": ["Ras signaling pathway", "MAPK signaling pathway", "PI3K-Akt signaling pathway"],
            "functions": ["细胞增殖", "分化"]
        }
    }
    
    # COSMIC突变数据库示例
    cosmic_data = {
        "PTEN": {
            "mutation": "true",
            "mutation_types": ["点突变", "缺失"],
            "frequency": "30%"
        },
        "TP53": {
            "mutation": "true",
            "mutation_types": ["点突变"],
            "frequency": "50%"
        },
        "CTNNB1": {
            "mutation": "true",
            "mutation_types": ["点突变"],
            "frequency": "20%"
        },
        "NRAS": {
            "mutation": "true",
            "mutation_types": ["点突变"],
            "frequency": "15%"
        },
        "CDKN2A": {
            "mutation": "true",
            "mutation_types": ["缺失", "点突变"],
            "frequency": "40%"
        }
    }
    
    with open(db_dir / "kegg.json", 'w', encoding='utf-8') as f:
        json.dump(kegg_data, f, ensure_ascii=False, indent=2)
    
    with open(db_dir / "cosmic.json", 'w', encoding='utf-8') as f:
        json.dump(cosmic_data, f, ensure_ascii=False, indent=2)
    
    print("示例数据库已创建")


def main():
    parser = argparse.ArgumentParser(description="数据库对比验证脚本")
    parser.add_argument("--create-samples", action="store_true", help="创建示例数据库")
    parser.add_argument("--databases", "-d", type=str, nargs="+", default=["kegg", "cosmic"],
                        help="要对比的数据库名称")
    parser.add_argument("--output", "-o", type=str, default="database_validation_report.json",
                        help="验证报告输出文件")
    args = parser.parse_args()
    
    if args.create_samples:
        create_sample_databases()
        return
    
    validator = DatabaseValidator()
    results = validator.run_database_validation(args.databases)
    
    if results:
        output_path = Path(__file__).parent / args.output
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n验证完成！报告已保存到: {output_path}")


if __name__ == "__main__":
    main()
