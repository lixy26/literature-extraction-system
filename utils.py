import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


def save_results(results: Dict[str, Any], output_path: Path) -> None:
    """
    保存处理结果到JSON文件
    
    Args:
        results: 处理结果数据
        output_path: 输出文件路径
    """
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到: {output_path}")
    except Exception as e:
        logger.error(f"保存结果失败: {str(e)}")
        raise


def load_results(input_path: Path) -> Dict[str, Any]:
    """
    从JSON文件加载处理结果
    
    Args:
        input_path: 输入文件路径
        
    Returns:
        加载的结果数据
    """
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"已从 {input_path} 加载结果")
        return data
    except Exception as e:
        logger.error(f"加载结果失败: {str(e)}")
        raise


def validate_api_key(api_key: str) -> bool:
    """
    验证API密钥是否有效（格式检查）
    
    Args:
        api_key: API密钥
        
    Returns:
        True如果格式有效，False否则
    """
    if not api_key or not isinstance(api_key, str):
        return False
    
    # 简单的格式检查
    if len(api_key) < 10:
        return False
    
    # 检查是否为默认占位符
    if api_key == "Your API Key":
        return False
    
    return True


def setup_logging(log_level: str = "INFO") -> None:
    """
    设置日志配置
    
    Args:
        log_level: 日志级别
    """
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.FileHandler("literature_extraction.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logger.info("日志系统已初始化")


def format_gene_summary(gene_name: str, gene_data: Dict[str, Any]) -> str:
    """
    格式化基因信息摘要
    
    Args:
        gene_name: 基因名称
        gene_data: 基因数据
        
    Returns:
        格式化的摘要字符串
    """
    summary = [f"基因: {gene_name}"]
    
    # 基本信息
    basic_info = gene_data.get("basic_info", {})
    if "gene_function_category" in basic_info:
        summary.append(f"  功能分类: {basic_info['gene_function_category']}")
    
    # 表达与预后
    exp_prog = gene_data.get("expression_and_prognosis", {})
    if "expression_level" in exp_prog:
        summary.append(f"  表达水平: {exp_prog['expression_level']}")
    
    # 靶向治疗
    therapy = gene_data.get("targeted_therapy", {})
    if "is_potential_target" in therapy:
        summary.append(f"  潜在靶点: {therapy['is_potential_target']}")
    
    # 生物学功能
    functions = gene_data.get("biological_functions", [])
    if functions:
        summary.append(f"  生物学功能: {', '.join(functions)}")
    
    # 参考文献
    ref = gene_data.get("reference", {})
    if "title" in ref:
        summary.append(f"  参考文献: {ref['title']}")
    if "year" in ref:
        summary.append(f"  年份: {ref['year']}")
    if "location" in ref:
        summary.append(f"  位置: {ref['location']}")
    
    return "\n".join(summary)