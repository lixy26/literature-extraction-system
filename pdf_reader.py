import pdfplumber
from pathlib import Path
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class PDFReader:
    """PDF文件读取器，负责从PDF中提取文本内容"""

    @staticmethod
    def extract_text_from_pdf(pdf_path: Path) -> Tuple[str, int]:
        """
        从PDF文件中提取文本内容
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            元组(提取的文本内容, 页码数)
            
        Raises:
            FileNotFoundError: 文件不存在
            Exception: 其他读取错误
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        text = ""
        page_count = 0
        
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                page_count = len(pdf.pages)
                for page_idx, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"【第{page_idx}页】\n{page_text}\n\n"
                
            logger.info(f"成功从 {pdf_path.name} 提取文本，共 {page_count} 页，{len(text)} 字符")
            return text.strip(), page_count
            
        except Exception as e:
            logger.error(f"读取PDF文件 {pdf_path.name} 时出错: {str(e)}")
            raise

    @staticmethod
    def split_text(text: str, max_length: int = 50000, overlap: int = 5000) -> List[str]:
        """
        将长文本分割成多个chunk，确保不超过模型输入限制
        
        Args:
            text: 原始文本
            max_length: 每个chunk的最大长度
            overlap: 相邻chunk之间的重叠长度
            
        Returns:
            分割后的文本chunk列表
        """
        chunks = []
        text_length = len(text)
        
        if text_length <= max_length:
            return [text]
        
        start = 0
        while start < text_length:
            end = start + max_length
            if end < text_length:
                # 找到合适的分割点（在段落或句子结束处）
                split_pos = text.rfind('\n\n', start, end)
                if split_pos == -1:
                    split_pos = text.rfind('\n', start, end)
                if split_pos == -1 or split_pos < start + overlap:
                    split_pos = end
                end = split_pos
            chunks.append(text[start:end])
            start = end - overlap
            if start < 0:
                start = 0
        
        logger.info(f"文本已分割为 {len(chunks)} 个chunk")
        return chunks

    @staticmethod
    def get_pdf_files(pdf_dir: Path, max_files: int = 20) -> List[Path]:
        """
        获取指定目录下的所有PDF文件
        
        Args:
            pdf_dir: PDF目录路径
            max_files: 最大返回文件数
            
        Returns:
            PDF文件路径列表
        """
        if not pdf_dir.exists():
            logger.warning(f"PDF目录不存在: {pdf_dir}")
            return []
        
        pdf_files = sorted(pdf_dir.glob("*.pdf"))[:max_files]
        logger.info(f"在 {pdf_dir} 找到 {len(pdf_files)} 个PDF文件")
        return pdf_files