#!/usr/bin/env python3
"""
KEGG数据抓取脚本

用于从KEGG数据库抓取基因-通路映射关系，构建本地评估知识库
遵循论文级可复现原则，一次性抓取后离线使用

使用方式：
1. 测试模式（使用示例数据）：python kegg_crawler.py --test
2. 完整抓取：python kegg_crawler.py
"""

import requests
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple
import time
import logging
import argparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# KEGG API 配置
KEGG_API_URL = "http://rest.kegg.jp"
KEGG_ORGANISM = "hsa"  # 人类

# 本地数据库配置
DB_PATH = Path(__file__).parent / "gene_kb.db"

# 输出目录
OUTPUT_DIR = Path(__file__).parent / "kegg_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 5


# 示例数据（用于测试模式，避免网络请求）
SAMPLE_KEGG_DATA = [
    {
        "pathway_id": "path:hsa04115",
        "pathway_name": "p53 signaling pathway",
        "genes": ["7157", "7158", "672", "7356", "836", "837", "838"],
        "gene_symbols": [("7157", "TP53"), ("7158", "TP63"), ("672", "ATM"), 
                        ("7356", "MDM2"), ("836", "CDKN1A"), ("837", "CDKN1B"), ("838", "CDKN2A")]
    },
    {
        "pathway_id": "path:hsa04150",
        "pathway_name": "PI3K-Akt signaling pathway",
        "genes": ["5290", "5291", "5292", "5294", "5295", "1956", "207"],
        "gene_symbols": [("5290", "PIK3CA"), ("5291", "PIK3CB"), ("5292", "PIK3CD"), 
                        ("5294", "PIK3R1"), ("5295", "PIK3R2"), ("1956", "AKT1"), ("207", "PTEN")]
    },
    {
        "pathway_id": "path:hsa04310",
        "pathway_name": "Wnt signaling pathway",
        "genes": ["7475", "7476", "7477", "7478", "7481", "7482", "8313"],
        "gene_symbols": [("7475", "WNT1"), ("7476", "WNT2"), ("7477", "WNT2B"), 
                        ("7478", "WNT3"), ("7481", "WNT5A"), ("7482", "WNT5B"), ("8313", "CTNNB1")]
    },
    {
        "pathway_id": "path:hsa04330",
        "pathway_name": "Notch signaling pathway",
        "genes": ["4851", "4852", "4853", "4854", "4855", "1324", "1325"],
        "gene_symbols": [("4851", "NOTCH1"), ("4852", "NOTCH2"), ("4853", "NOTCH3"), 
                        ("4854", "NOTCH4"), ("4855", "NOTCHNL1"), ("1324", "HES1"), ("1325", "HES5")]
    },
    {
        "pathway_id": "path:hsa04010",
        "pathway_name": "MAPK signaling pathway",
        "genes": ["5594", "5595", "5596", "5604", "5607", "5608", "5609"],
        "gene_symbols": [("5594", "MAPK1"), ("5595", "MAPK3"), ("5596", "MAPK4"), 
                        ("5604", "MAPK8"), ("5607", "MAPK10"), ("5608", "MAPK11"), ("5609", "MAPK12")]
    }
]


class KEGGCrawler:
    """KEGG数据抓取器"""
    
    def __init__(self):
        # 创建带重试机制的session
        self.session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_DELAY,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        
        self.timeout = 60
        self.request_delay = 0.5
    
    def _make_request(self, endpoint: str, params: dict = None) -> str:
        """发送请求到KEGG API（带重试）"""
        url = f"{KEGG_API_URL}/{endpoint}"
        
        try:
            time.sleep(self.request_delay)
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败 {url}: {e}")
            return ""
    
    def get_pathway_list(self) -> List[str]:
        """获取所有人类通路列表"""
        logger.info("获取KEGG通路列表...")
        result = self._make_request(f"list/pathway/{KEGG_ORGANISM}")
        
        pathways = []
        for line in result.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    pathway_id = parts[0].strip()
                    pathway_name = parts[1].strip()
                    pathways.append((pathway_id, pathway_name))
        
        logger.info(f"获取到 {len(pathways)} 条通路")
        return pathways
    
    def get_pathway_genes(self, pathway_id: str) -> List[str]:
        """获取指定通路中的基因列表"""
        logger.debug(f"获取通路 {pathway_id} 的基因...")
        result = self._make_request(f"link/hsa/{pathway_id}")
        
        genes = []
        for line in result.strip().split('\n'):
            if line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    gene_id = parts[1].strip()
                    if gene_id.startswith('hsa:'):
                        gene_id = gene_id[4:]
                    if gene_id.isdigit():
                        genes.append(gene_id)
        
        return genes
    
    def get_gene_info(self, gene_id: str) -> Dict[str, str]:
        """获取基因详细信息"""
        if not gene_id.isdigit():
            return {
                "gene_id": gene_id,
                "gene_name": "",
                "symbol": "",
                "description": ""
            }
        
        result = self._make_request(f"get/{KEGG_ORGANISM}:{gene_id}")
        
        info = {
            "gene_id": gene_id,
            "gene_name": "",
            "symbol": "",
            "description": ""
        }
        
        for line in result.strip().split('\n'):
            if line.startswith('NAME'):
                parts = line[5:].strip().split('//')
                info["gene_name"] = parts[0].strip()
                if len(parts) > 1:
                    info["description"] = parts[1].strip()
            elif line.startswith('SYMBOL'):
                info["symbol"] = line[7:].strip()
        
        return info
    
    def crawl_all_pathways(self, max_pathways: int = None) -> List[Dict[str, any]]:
        """抓取所有通路及其基因"""
        pathways = self.get_pathway_list()
        
        if max_pathways:
            pathways = pathways[:max_pathways]
            logger.info(f"限制抓取前 {max_pathways} 条通路")
        
        all_data = []
        skipped_count = 0
        
        for i, (pathway_id, pathway_name) in enumerate(pathways, 1):
            try:
                genes = self.get_pathway_genes(pathway_id)
                gene_symbols = []
                
                for gene_id in genes:
                    gene_info = self.get_gene_info(gene_id)
                    if gene_info["symbol"]:
                        gene_symbols.append((gene_id, gene_info["symbol"]))
                
                all_data.append({
                    "pathway_id": pathway_id,
                    "pathway_name": pathway_name,
                    "genes": genes,
                    "gene_symbols": gene_symbols
                })
                
                logger.info(f"[{i}/{len(pathways)}] 完成通路 {pathway_id}: {len(genes)} 个基因")
            
            except Exception as e:
                logger.error(f"[{i}/{len(pathways)}] 处理通路 {pathway_id} 失败: {e}")
                skipped_count += 1
        
        logger.info(f"抓取完成，共 {len(all_data)} 条通路")
        return all_data


class GeneKBBuilder:
    """基因知识库构建器"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
    
    def create_tables(self):
        """创建数据库表"""
        cursor = self.conn.cursor()
        
        # 基因-通路表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gene_pathway (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id TEXT NOT NULL,
                gene_symbol TEXT,
                pathway_id TEXT NOT NULL,
                pathway_name TEXT NOT NULL,
                UNIQUE(gene_id, pathway_id)
            )
        ''')
        
        # 通路别名映射表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pathway_alias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_name TEXT NOT NULL,
                pathway_id TEXT NOT NULL,
                alias TEXT NOT NULL,
                UNIQUE(pathway_id, alias)
            )
        ''')
        
        # 基因信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gene_info (
                gene_id TEXT PRIMARY KEY,
                gene_name TEXT,
                gene_symbol TEXT UNIQUE,
                description TEXT
            )
        ''')
        
        self.conn.commit()
        logger.info("数据库表创建完成")
    
    def insert_pathway_data(self, pathway_data: List[Dict[str, any]]):
        """插入通路数据"""
        cursor = self.conn.cursor()
        
        for pathway in pathway_data:
            pathway_id = pathway["pathway_id"]
            pathway_name = pathway["pathway_name"]
            
            # 插入基因-通路关系
            for gene_id, gene_symbol in pathway["gene_symbols"]:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO gene_pathway
                        (gene_id, gene_symbol, pathway_id, pathway_name)
                        VALUES (?, ?, ?, ?)
                    ''', (gene_id, gene_symbol, pathway_id, pathway_name))
                except Exception as e:
                    logger.warning(f"插入基因-通路失败 {gene_id}-{pathway_id}: {e}")
            
            # 插入通路别名
            aliases = self._generate_pathway_aliases(pathway_name)
            for alias in aliases:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO pathway_alias
                        (standard_name, pathway_id, alias)
                        VALUES (?, ?, ?)
                    ''', (pathway_name, pathway_id, alias))
                except Exception as e:
                    logger.warning(f"插入通路别名失败 {pathway_id}-{alias}: {e}")
        
        self.conn.commit()
        logger.info("通路数据插入完成")
    
    def insert_gene_info(self, gene_info_list: List[Dict[str, str]]):
        """插入基因信息"""
        cursor = self.conn.cursor()
        
        for gene_info in gene_info_list:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO gene_info
                    (gene_id, gene_name, gene_symbol, description)
                    VALUES (?, ?, ?, ?)
                ''', (
                    gene_info["gene_id"],
                    gene_info["gene_name"],
                    gene_info["symbol"],
                    gene_info["description"]
                ))
            except Exception as e:
                logger.warning(f"插入基因信息失败 {gene_info['gene_id']}: {e}")
        
        self.conn.commit()
        logger.info("基因信息插入完成")
    
    def _generate_pathway_aliases(self, pathway_name: str) -> List[str]:
        """生成通路名称的各种别名形式"""
        aliases = set()
        aliases.add(pathway_name)
        
        # 移除物种前缀
        if pathway_name.startswith("Homo sapiens "):
            base_name = pathway_name[14:]
            aliases.add(base_name)
        else:
            base_name = pathway_name
        
        # 移除后缀变体
        lower_name = base_name.lower()
        if lower_name.endswith(" pathway"):
            aliases.add(base_name[:-8])
            aliases.add(base_name[:-8] + " signaling")
        if lower_name.endswith(" signaling pathway"):
            aliases.add(base_name[:-18])
            aliases.add(base_name[:-18] + " pathway")
        if lower_name.endswith(" signaling"):
            aliases.add(base_name[:-10])
        
        # 标准化变体
        standard_variants = []
        for alias in aliases:
            standard_variants.append(alias.replace(" - ", "-"))
            standard_variants.append(alias.replace("-", "/"))
            standard_variants.append(alias.replace("/", "-"))
            standard_variants.append(alias.replace(" ", ""))
            standard_variants.append(alias.replace(" ", "-"))
        aliases.update(standard_variants)
        aliases.update([a.lower() for a in aliases])
        
        return list(aliases)
    
    def create_indexes(self):
        """创建索引"""
        cursor = self.conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene_pathway_gene ON gene_pathway(gene_symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene_pathway_pathway ON gene_pathway(pathway_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pathway_alias_alias ON pathway_alias(alias)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene_info_symbol ON gene_info(gene_symbol)')
        self.conn.commit()
        logger.info("索引创建完成")
    
    def verify_database(self):
        """验证数据库内容"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM gene_pathway')
        gp_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT gene_symbol) FROM gene_pathway')
        gene_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT pathway_id) FROM gene_pathway')
        pathway_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM pathway_alias')
        alias_count = cursor.fetchone()[0]
        
        logger.info(f"=== 数据库验证 ===")
        logger.info(f"基因-通路关系数: {gp_count}")
        logger.info(f"涉及基因数: {gene_count}")
        logger.info(f"涉及通路数: {pathway_count}")
        logger.info(f"通路别名数: {alias_count}")


def main():
    parser = argparse.ArgumentParser(description="KEGG数据抓取脚本")
    parser.add_argument("--test", action="store_true", help="使用示例数据（无需网络）")
    parser.add_argument("--max-pathways", type=int, default=None, help="限制抓取的通路数量")
    args = parser.parse_args()
    
    builder = GeneKBBuilder(DB_PATH)
    
    try:
        if args.test:
            # 使用示例数据
            logger.info("使用示例数据构建数据库...")
            pathway_data = SAMPLE_KEGG_DATA
            
            # 保存示例数据
            raw_data_file = OUTPUT_DIR / "kegg_raw_data.json"
            with open(raw_data_file, 'w', encoding='utf-8') as f:
                json.dump(pathway_data, f, ensure_ascii=False, indent=2)
            logger.info(f"示例数据已保存到 {raw_data_file}")
        else:
            # 实时抓取
            logger.info("开始抓取KEGG数据...")
            crawler = KEGGCrawler()
            pathway_data = crawler.crawl_all_pathways(max_pathways=args.max_pathways)
            
            raw_data_file = OUTPUT_DIR / "kegg_raw_data.json"
            with open(raw_data_file, 'w', encoding='utf-8') as f:
                json.dump(pathway_data, f, ensure_ascii=False, indent=2)
            logger.info(f"抓取数据已保存到 {raw_data_file}")
        
        # 构建数据库
        logger.info("开始构建数据库...")
        builder.connect()
        builder.create_tables()
        builder.insert_pathway_data(pathway_data)
        
        # 生成基因信息
        gene_info_list = []
        seen_genes = set()
        
        for pathway in pathway_data:
            for gene_id, gene_symbol in pathway["gene_symbols"]:
                if gene_id not in seen_genes:
                    gene_info_list.append({
                        "gene_id": gene_id,
                        "gene_name": gene_symbol,
                        "symbol": gene_symbol,
                        "description": ""
                    })
                    seen_genes.add(gene_id)
        
        builder.insert_gene_info(gene_info_list)
        builder.create_indexes()
        builder.verify_database()
        
        logger.info(f"数据库构建完成！文件位置: {DB_PATH}")
        
    except Exception as e:
        logger.error(f"执行失败: {e}")
        raise
    finally:
        builder.close()


if __name__ == "__main__":
    main()
