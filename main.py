#!/usr/bin/env python3
"""
肝癌文献基因信息提取系统主入口

功能：
1. 批量读取指定工作路径下所有PDF格式文献
2. 调用大语言模型进行文献内容智能解析
3. 针对肝癌细胞相关基因信息进行结构化提取
4. 输出符合规范的JSON格式文件

使用方法：
1. 将PDF文献放入 pdfs/ 目录
2. 在 config.py 中配置API密钥
3. 运行: python main.py
"""

import logging
from pathlib import Path
from datetime import datetime
from config import PDF_DIR, OUTPUT_DIR, MAX_PDFS, MAX_WORKERS
from processor import LiteratureProcessor
from utils import save_results, setup_logging, validate_api_key, format_gene_summary

logger = logging.getLogger(__name__)


def main():
    """主函数"""
    # 初始化日志
    setup_logging("INFO")
    
    logger.info("=" * 60)
    logger.info("肝癌文献基因信息提取系统启动")
    logger.info("=" * 60)
    
    # 检查API密钥
    from config import API_KEY
    if not validate_api_key(API_KEY):
        logger.error("API密钥无效！请在 config.py 中配置有效的API密钥")
        logger.error("使用前请访问 https://dashscope.aliyuncs.com/ 获取API密钥")
        return
    
    # 检查PDF目录
    if not PDF_DIR.exists():
        logger.error(f"PDF目录不存在: {PDF_DIR}")
        logger.error("请在项目目录下创建 pdfs/ 文件夹并放入PDF文献")
        return
    
    # 创建处理器
    processor = LiteratureProcessor()
    
    # 批量处理PDF
    logger.info(f"开始处理PDF目录: {PDF_DIR}")
    results = processor.batch_process(PDF_DIR, max_files=MAX_PDFS)
    
    if not results:
        logger.warning("未处理任何PDF文件")
        return
    
    # 按基因名称组织结果
    logger.info("按基因名称组织提取结果")
    organized_results = processor.organize_by_gene(results)
    
    # 生成输出数据结构
    output_data = {
        "metadata": {
            "total_genes": len(organized_results),
            "total_pdfs_processed": len(results),
            "processing_date": datetime.now().strftime("%Y-%m-%d")
        },
        "genes": organized_results
    }
    
    # 保存结果
    output_path = OUTPUT_DIR / "gene_extraction_results.json"
    save_results(output_data, output_path)
    
    # 打印处理摘要
    logger.info("=" * 60)
    logger.info("处理完成！")
    logger.info("=" * 60)
    logger.info(f"共处理 {len(results)} 个PDF文件")
    logger.info(f"共提取 {len(organized_results)} 个基因")
    logger.info(f"结果已保存到: {output_path}")
    
    # 打印基因摘要
    logger.info("\n--- 基因提取摘要 ---")
    for gene_name, gene_data in organized_results.items():
        logger.info(format_gene_summary(gene_name, gene_data))
        logger.info("-" * 40)


if __name__ == "__main__":
    main()