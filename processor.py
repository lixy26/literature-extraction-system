import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from pdf_reader import PDFReader
from llm_client import LLMClient
from prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class LiteratureProcessor:
    """文献处理器，负责协调PDF读取、LLM调用和结果整合"""

    def __init__(self):
        self.pdf_reader = PDFReader()
        self.llm_client = LLMClient()
        self.output_dir = Path(__file__).parent / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.pdf_results_dir = self.output_dir / "pdf_results"
        self.pdf_results_dir.mkdir(exist_ok=True)

    def save_raw_response(self, pdf_name: str, content: str):
        """保存API原始响应到文件"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{pdf_name}_raw_response_{timestamp}.txt"
        filepath = self.output_dir / filename
        try:
            logger.info(f"准备保存原始响应，内容长度: {len(content)}")
            logger.info(f"内容前200字符: {content[:200]}")
            with open(filepath, 'w', encoding='utf-8') as f:
                written = f.write(content)
                logger.info(f"实际写入字符数: {written}")
            logger.info(f"原始响应已保存到: {filepath}")
            # 验证文件内容
            with open(filepath, 'r', encoding='utf-8') as f:
                saved_content = f.read()
                logger.info(f"验证：文件保存了 {len(saved_content)} 字符")
        except Exception as e:
            logger.error(f"保存原始响应失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

    def process_single_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        处理单个PDF文件
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            处理结果字典
        """
        logger.info(f"开始处理PDF: {pdf_path.name}")
        
        try:
            # 提取PDF文本
            pdf_text, page_count = self.pdf_reader.extract_text_from_pdf(pdf_path)
            
            if not pdf_text:
                logger.warning(f"PDF文件 {pdf_path.name} 提取文本为空")
                return {
                    "pdf_file": pdf_path.name,
                    "pdf_path": str(pdf_path),
                    "page_count": 0,
                    "status": "empty_text",
                    "gene_count": 0,
                    "genes": []
                }
            
            # 处理长文本
            if len(pdf_text) > 200000:
                logger.warning(f"PDF文件 {pdf_path.name} 文本过长（{len(pdf_text)}字符），将进行分块处理")
                chunks = self.pdf_reader.split_text(pdf_text)
                all_genes = []
                
                for i, chunk in enumerate(chunks):
                    logger.info(f"处理第 {i + 1}/{len(chunks)} 个文本块")
                    result = self.llm_client.extract_gene_info(chunk)
                    # 检查result是否为有效字典且包含genes字段
                    if result and isinstance(result, dict) and "genes" in result:
                        genes = result["genes"]
                        if isinstance(genes, list):
                            all_genes.extend(genes)
                        else:
                            logger.warning(f"第 {i + 1} 个文本块的genes字段不是列表类型")
                    elif result:
                        logger.warning(f"第 {i + 1} 个文本块API返回格式异常: {str(result)[:200]}")
                
                # 合并重复基因（基于gene_name）
                merged_genes = self._merge_duplicate_genes(all_genes)
            else:
                # 直接调用API
                logger.info("开始调用API...")
                result = self.llm_client.extract_gene_info(pdf_text)
                
                # 调试：查看API返回结果的结构
                logger.info(f"API返回类型: {type(result)}")
                if isinstance(result, dict):
                    logger.info(f"API返回的字典键: {list(result.keys())}")
                    logger.info(f"API返回内容前300字符: {str(result)[:300]}")
                else:
                    logger.info(f"API返回内容: {str(result)[:300]}")
                
                # 检查result是否为有效字典
                if result and isinstance(result, dict) and "genes" in result:
                    merged_genes = result["genes"]
                    logger.info(f"成功获取genes字段，类型: {type(merged_genes)}")
                    # 确保genes是列表
                    if not isinstance(merged_genes, list):
                        logger.warning(f"genes字段不是列表类型: {type(merged_genes)}")
                        merged_genes = []
                    else:
                        logger.info(f"genes是列表，长度: {len(merged_genes)}")
                        if len(merged_genes) > 0:
                            logger.info(f"第一个基因对象的键: {list(merged_genes[0].keys()) if isinstance(merged_genes[0], dict) else merged_genes[0]}")
                else:
                    merged_genes = []
                    if result:
                        # 如果返回了原始响应，保存到文件
                        if isinstance(result, dict) and "raw_response" in result:
                            logger.warning("API返回了原始文本，保存到文件...")
                            self.save_raw_response(
                                pdf_path.stem, 
                                result["raw_response"]
                            )
                        else:
                            logger.warning(f"API返回格式异常: {str(result)[:500]}")
                            # 保存实际返回的JSON结构以便调试
                            self.save_raw_response(
                                pdf_path.stem, 
                                json.dumps(result, ensure_ascii=False, indent=2)
                            )
            
            # 为每条基因添加上下文信息
            for gene in merged_genes:
                gene["source_pdf"] = pdf_path.name
                gene["source_pdf_path"] = str(pdf_path)
                if "reference" not in gene:
                    gene["reference"] = {}
                gene["reference"]["pdf_file"] = pdf_path.name
                # 记录来源PDF的处理时间
                gene["extraction_time"] = datetime.now().isoformat()
            
            result = {
                "pdf_file": pdf_path.name,
                "pdf_path": str(pdf_path),
                "page_count": page_count,
                "status": "ok",
                "gene_count": len(merged_genes),
                "genes": merged_genes,
                "extraction_time": datetime.now().isoformat()
            }
            
            # 单独保存每个PDF的结果
            self._save_pdf_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"处理PDF文件 {pdf_path.name} 时出错: {str(e)}")
            return {
                "pdf_file": pdf_path.name,
                "pdf_path": str(pdf_path),
                "page_count": 0,
                "status": "error",
                "gene_count": 0,
                "genes": [],
                "error": str(e)
            }

    def _merge_duplicate_genes(self, genes: List[Dict]) -> List[Dict]:
        """
        合并重复的基因条目
        
        Args:
            genes: 基因列表
            
        Returns:
            去重后的基因列表
        """
        gene_map = {}
        
        for gene in genes:
            gene_name = gene.get("gene_name", "").strip()
            if not gene_name:
                continue
            
            if gene_name not in gene_map:
                gene_map[gene_name] = gene
            else:
                # 合并信息
                existing = gene_map[gene_name]
                
                # 合并生物学功能
                existing_funcs = set(existing.get("biological_functions", []))
                new_funcs = set(gene.get("biological_functions", []))
                existing["biological_functions"] = list(existing_funcs.union(new_funcs))
                
                # 合并位置信息
                if "reference" in gene:
                    if "location" in gene["reference"]:
                        existing_loc = existing["reference"].get("location", "")
                        new_loc = gene["reference"]["location"]
                        if existing_loc and new_loc and new_loc not in existing_loc:
                            existing["reference"]["location"] = f"{existing_loc}; {new_loc}"
        
        return list(gene_map.values())

    def batch_process(self, pdf_dir: Path, max_files: int = 20) -> List[Dict[str, Any]]:
        """
        批量处理PDF文件
        
        Args:
            pdf_dir: PDF目录
            max_files: 最大处理文件数
            
        Returns:
            处理结果列表
        """
        pdf_files = self.pdf_reader.get_pdf_files(pdf_dir, max_files)
        
        if not pdf_files:
            logger.warning("未找到PDF文件")
            return []
        
        logger.info(f"开始批量处理 {len(pdf_files)} 个PDF文件")
        results = []
        
        for pdf_file in pdf_files:
            result = self.process_single_pdf(pdf_file)
            results.append(result)
            logger.info(f"完成处理: {pdf_file.name} | 状态: {result['status']} | 基因数: {result['gene_count']}")
        
        return results

    def organize_by_gene(self, results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        按基因名称组织提取结果
        
        Args:
            results: 批量处理结果
            
        Returns:
            按基因名称分类的字典
        """
        gene_dict = {}
        
        for result in results:
            genes = result.get("genes", [])
            for gene in genes:
                gene_name = gene.get("gene_name", "unknown").strip()
                if gene_name not in gene_dict:
                    gene_dict[gene_name] = []
                gene_dict[gene_name].append(gene)
        
        # 对每个基因的多个条目进行合并
        organized = {}
        for gene_name, entries in gene_dict.items():
            if len(entries) == 1:
                organized[gene_name] = entries[0]
            else:
                organized[gene_name] = self._merge_entries(entries)
        
        return organized

    def _save_pdf_result(self, result: Dict):
        """
        单独保存每个PDF的处理结果
        
        Args:
            result: 单个PDF的处理结果
        """
        try:
            pdf_name = result["pdf_file"].replace(".pdf", "")
            filename = f"{pdf_name}_result.json"
            filepath = self.pdf_results_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            logger.info(f"单个PDF结果已保存到: {filepath}")
        except Exception as e:
            logger.error(f"保存单个PDF结果失败: {e}")

    def _merge_entries(self, entries: List[Dict]) -> Dict:
        """
        合并同一基因的多个条目，综合来自不同文献的信息
        
        Args:
            entries: 同一基因的多个条目（来自不同PDF）
            
        Returns:
            合并后的条目，包含所有来源的综合信息
        """
        merged = entries[0].copy()
        
        # 初始化来源追踪
        merged["sources"] = []
        
        for entry in entries:
            # 添加来源信息
            source_info = {
                "pdf_file": entry.get("source_pdf", ""),
                "pdf_path": entry.get("source_pdf_path", ""),
                "extraction_time": entry.get("extraction_time", "")
            }
            if source_info not in merged["sources"]:
                merged["sources"].append(source_info)
            
            # 合并生物学功能
            merged_funcs = set(merged.get("biological_functions", []))
            entry_funcs = set(entry.get("biological_functions", []))
            merged["biological_functions"] = list(merged_funcs.union(entry_funcs))
            
            # 合并位置信息
            if "reference" in entry:
                merged_ref = merged.get("reference", {})
                entry_ref = entry.get("reference", {})
                
                if "location" in entry_ref:
                    merged_loc = merged_ref.get("location", "")
                    entry_loc = entry_ref["location"]
                    if merged_loc and entry_loc and entry_loc not in merged_loc:
                        merged_ref["location"] = f"{merged_loc}; {entry_loc}"
                    elif entry_loc:
                        merged_ref["location"] = entry_loc
                
                # 合并参考文献标题（收集所有不同标题）
                if "title" in entry_ref and entry_ref["title"] and entry_ref["title"] != "未提及":
                    if "title" not in merged_ref or not merged_ref["title"] or merged_ref["title"] == "未提及":
                        merged_ref["title"] = entry_ref["title"]
                    elif entry_ref["title"] != merged_ref["title"]:
                        # 多个文献来源，合并标题
                        merged_ref["title"] = f"{merged_ref['title']}; {entry_ref['title']}"
                
                # 合并年份
                if "year" in entry_ref and entry_ref["year"] and entry_ref["year"] != "未提及":
                    if "year" not in merged_ref or not merged_ref["year"] or merged_ref["year"] == "未提及":
                        merged_ref["year"] = entry_ref["year"]
                    elif entry_ref["year"] != merged_ref["year"]:
                        merged_ref["year"] = f"{merged_ref['year']}, {entry_ref['year']}"
            
            # 合并表达与预后信息
            if "expression_and_prognosis" in entry:
                merged_exp = merged.get("expression_and_prognosis", {})
                entry_exp = entry.get("expression_and_prognosis", {})
                
                # 合并表达水平（收集所有不同说法）
                if "expression_level" in entry_exp and entry_exp["expression_level"] != "未提及":
                    if "expression_level" not in merged_exp or not merged_exp["expression_level"] or merged_exp["expression_level"] == "未提及":
                        merged_exp["expression_level"] = entry_exp["expression_level"]
                    elif entry_exp["expression_level"] != merged_exp["expression_level"]:
                        merged_exp["expression_level"] = f"{merged_exp['expression_level']}; {entry_exp['expression_level']}"
                
                # 合并预后相关性
                if "prognosis_correlation" in entry_exp:
                    merged_prog = merged_exp.get("prognosis_correlation", {})
                    entry_prog = entry_exp.get("prognosis_correlation", {})
                    
                    for key in ["OS", "DFS"]:
                        if key in entry_prog and entry_prog[key] != "未提及":
                            if key not in merged_prog or not merged_prog[key] or merged_prog[key] == "未提及":
                                merged_prog[key] = entry_prog[key]
                            elif entry_prog[key] != merged_prog[key]:
                                merged_prog[key] = f"{merged_prog[key]}; {entry_prog[key]}"
                    merged_exp["prognosis_correlation"] = merged_prog
                
                # 合并临床病理关联
                if "clinicopathological_correlation" in entry_exp and entry_exp["clinicopathological_correlation"] != "未提及":
                    merged_corr = merged_exp.get("clinicopathological_correlation", "")
                    entry_corr = entry_exp["clinicopathological_correlation"]
                    if merged_corr and entry_corr and entry_corr not in merged_corr:
                        merged_exp["clinicopathological_correlation"] = f"{merged_corr}; {entry_corr}"
                    elif entry_corr:
                        merged_exp["clinicopathological_correlation"] = entry_corr
                
                merged["expression_and_prognosis"] = merged_exp
            
            # 合并靶向药物信息
            if "targeted_therapy" in entry:
                merged_therapy = merged.get("targeted_therapy", {})
                entry_therapy = entry.get("targeted_therapy", {})
                
                if "is_potential_target" in entry_therapy and entry_therapy["is_potential_target"] != "未提及":
                    if "is_potential_target" not in merged_therapy or not merged_therapy["is_potential_target"] or merged_therapy["is_potential_target"] == "未提及":
                        merged_therapy["is_potential_target"] = entry_therapy["is_potential_target"]
                
                if "known_drugs" in entry_therapy and entry_therapy["known_drugs"] and entry_therapy["known_drugs"] != "未提及":
                    if "known_drugs" not in merged_therapy or not merged_therapy["known_drugs"] or merged_therapy["known_drugs"] == "未提及":
                        merged_therapy["known_drugs"] = entry_therapy["known_drugs"]
                    elif entry_therapy["known_drugs"] != merged_therapy["known_drugs"]:
                        merged_therapy["known_drugs"] = f"{merged_therapy['known_drugs']}; {entry_therapy['known_drugs']}"
                
                if "drug_resistance" in entry_therapy and entry_therapy["drug_resistance"] and entry_therapy["drug_resistance"] != "未提及":
                    merged_resist = merged_therapy.get("drug_resistance", "")
                    entry_resist = entry_therapy["drug_resistance"]
                    if merged_resist and entry_resist and entry_resist not in merged_resist:
                        merged_therapy["drug_resistance"] = f"{merged_resist}; {entry_resist}"
                    elif entry_resist:
                        merged_therapy["drug_resistance"] = entry_resist
                
                merged["targeted_therapy"] = merged_therapy
            
            # 合并突变信息
            if "mutation_and_epigenetics" in entry:
                merged_mutation = merged.get("mutation_and_epigenetics", {})
                entry_mutation = entry.get("mutation_and_epigenetics", {})
                
                if "mutation_types" in entry_mutation and entry_mutation["mutation_types"] and entry_mutation["mutation_types"] != "未提及":
                    if "mutation_types" not in merged_mutation or not merged_mutation["mutation_types"] or merged_mutation["mutation_types"] == "未提及":
                        merged_mutation["mutation_types"] = entry_mutation["mutation_types"]
                    elif entry_mutation["mutation_types"] != merged_mutation["mutation_types"]:
                        merged_mutation["mutation_types"] = f"{merged_mutation['mutation_types']}; {entry_mutation['mutation_types']}"
                
                if "mutation_frequency" in entry_mutation and entry_mutation["mutation_frequency"] and entry_mutation["mutation_frequency"] != "未提及":
                    if "mutation_frequency" not in merged_mutation or not merged_mutation["mutation_frequency"] or merged_mutation["mutation_frequency"] == "未提及":
                        merged_mutation["mutation_frequency"] = entry_mutation["mutation_frequency"]
                    elif entry_mutation["mutation_frequency"] != merged_mutation["mutation_frequency"]:
                        merged_mutation["mutation_frequency"] = f"{merged_mutation['mutation_frequency']}; {entry_mutation['mutation_frequency']}"
                
                merged["mutation_and_epigenetics"] = merged_mutation
        
        return merged