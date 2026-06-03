#!/usr/bin/env python3
"""
JSON结果整合到SQLite数据库工具

功能：
1. 读取所有PDF单独输出的JSON结果
2. 将多个文献的基因信息整合到SQLite数据库
3. 支持按基因名称聚合来自不同文献的信息
4. 提供查询接口方便后续分析
"""

import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GeneInfoDatabase:
    """基因信息数据库管理类"""

    def __init__(self, db_path: str = "gene_info.sqlite3"):
        self.db_path = Path(db_path)
        self.conn = None
        self._init_database()

    def _init_database(self):
        """初始化数据库表结构"""
        self.conn = sqlite3.connect(str(self.db_path))
        cursor = self.conn.cursor()

        # 创建文献表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file TEXT UNIQUE NOT NULL,
                pdf_path TEXT,
                page_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ok',
                gene_count INTEGER DEFAULT 0,
                extraction_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建基因基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS genes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_name TEXT UNIQUE NOT NULL,
                gene_function_category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 创建表达与预后信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expression_prognosis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                expression_level TEXT,
                prognosis_os TEXT,
                prognosis_dfs TEXT,
                clinicopathological_correlation TEXT,
                location TEXT,
                FOREIGN KEY(gene_id) REFERENCES genes(id),
                FOREIGN KEY(document_id) REFERENCES documents(id),
                UNIQUE(gene_id, document_id)
            )
        ''')

        # 创建靶向治疗信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS targeted_therapy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                is_potential_target TEXT,
                known_drugs TEXT,
                drug_resistance TEXT,
                FOREIGN KEY(gene_id) REFERENCES genes(id),
                FOREIGN KEY(document_id) REFERENCES documents(id),
                UNIQUE(gene_id, document_id)
            )
        ''')

        # 创建突变与表观遗传信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mutation_epigenetics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                mutation_types TEXT,
                mutation_frequency TEXT,
                FOREIGN KEY(gene_id) REFERENCES genes(id),
                FOREIGN KEY(document_id) REFERENCES documents(id),
                UNIQUE(gene_id, document_id)
            )
        ''')

        # 创建生物学功能表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS biological_functions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id INTEGER NOT NULL,
                function_name TEXT NOT NULL,
                document_id INTEGER NOT NULL,
                FOREIGN KEY(gene_id) REFERENCES genes(id),
                FOREIGN KEY(document_id) REFERENCES documents(id),
                UNIQUE(gene_id, function_name, document_id)
            )
        ''')

        # 创建参考文献表（使用gene_references避免SQLite保留关键字references）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gene_references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                title TEXT,
                year TEXT,
                location TEXT,
                FOREIGN KEY(gene_id) REFERENCES genes(id),
                FOREIGN KEY(document_id) REFERENCES documents(id),
                UNIQUE(gene_id, document_id)
            )
        ''')

        # 创建机制与模型表（信号通路、癌症亚型、实验模型等）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mechanisms_and_models (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene_id INTEGER NOT NULL,
                document_id INTEGER NOT NULL,
                signaling_pathways TEXT,
                cancer_subtype TEXT,
                experimental_model TEXT,
                evidence_level TEXT,
                FOREIGN KEY(gene_id) REFERENCES genes(id),
                FOREIGN KEY(document_id) REFERENCES documents(id),
                UNIQUE(gene_id, document_id)
            )
        ''')

        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_genes_name ON genes(gene_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_file ON documents(pdf_file)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_expression_gene ON expression_prognosis(gene_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_therapy_gene ON targeted_therapy(gene_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mutation_gene ON mutation_epigenetics(gene_id)')

        self.conn.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def insert_document(self, pdf_file: str, pdf_path: str, page_count: int, 
                        status: str, gene_count: int, extraction_time: str) -> int:
        """插入文献记录，返回document_id"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO documents 
                (pdf_file, pdf_path, page_count, status, gene_count, extraction_time)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (pdf_file, pdf_path, page_count, status, gene_count, extraction_time))
            self.conn.commit()
            cursor.execute('SELECT id FROM documents WHERE pdf_file = ?', (pdf_file,))
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"插入文献失败: {e}")
            return -1

    def insert_gene(self, gene_name: str, gene_function_category: str) -> int:
        """插入基因记录，返回gene_id"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO genes (gene_name, gene_function_category)
                VALUES (?, ?)
            ''', (gene_name, gene_function_category))
            self.conn.commit()
            cursor.execute('SELECT id FROM genes WHERE gene_name = ?', (gene_name,))
            return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"插入基因失败: {e}")
            return -1

    def insert_expression_prognosis(self, gene_id: int, document_id: int, data: Dict):
        """插入表达与预后信息"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO expression_prognosis
                (gene_id, document_id, expression_level, prognosis_os, 
                 prognosis_dfs, clinicopathological_correlation, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                gene_id,
                document_id,
                data.get('expression_level', ''),
                data.get('prognosis_correlation', {}).get('OS', ''),
                data.get('prognosis_correlation', {}).get('DFS', ''),
                data.get('clinicopathological_correlation', ''),
                data.get('location', '')
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"插入表达预后信息失败: {e}")

    def insert_targeted_therapy(self, gene_id: int, document_id: int, data: Dict):
        """插入靶向治疗信息"""
        cursor = self.conn.cursor()
        try:
            # 将列表转换为字符串
            known_drugs = data.get('known_drugs', '')
            if isinstance(known_drugs, list):
                known_drugs = '; '.join(str(d) for d in known_drugs)
            
            cursor.execute('''
                INSERT OR REPLACE INTO targeted_therapy
                (gene_id, document_id, is_potential_target, known_drugs, drug_resistance)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                gene_id,
                document_id,
                data.get('is_potential_target', ''),
                known_drugs,
                data.get('drug_resistance', '')
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"插入靶向治疗信息失败: {e}")

    def insert_mutation_epigenetics(self, gene_id: int, document_id: int, data: Dict):
        """插入突变与表观遗传信息"""
        cursor = self.conn.cursor()
        try:
            # 将列表转换为字符串
            mutation_types = data.get('mutation_types', '')
            if isinstance(mutation_types, list):
                mutation_types = '; '.join(str(m) for m in mutation_types)
            
            mutation_frequency = data.get('mutation_frequency', '')
            if isinstance(mutation_frequency, list):
                mutation_frequency = '; '.join(str(m) for m in mutation_frequency)
            
            cursor.execute('''
                INSERT OR REPLACE INTO mutation_epigenetics
                (gene_id, document_id, mutation_types, mutation_frequency)
                VALUES (?, ?, ?, ?)
            ''', (
                gene_id,
                document_id,
                mutation_types,
                mutation_frequency
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"插入突变信息失败: {e}")

    def insert_biological_functions(self, gene_id: int, document_id: int, functions: List[str]):
        """插入生物学功能"""
        cursor = self.conn.cursor()
        try:
            for func in functions:
                cursor.execute('''
                    INSERT OR IGNORE INTO biological_functions
                    (gene_id, function_name, document_id)
                    VALUES (?, ?, ?)
                ''', (gene_id, func, document_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"插入生物学功能失败: {e}")

    def insert_reference(self, gene_id: int, document_id: int, data: Dict):
        """插入参考文献信息"""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO gene_references
                (gene_id, document_id, title, year, location)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                gene_id,
                document_id,
                data.get('title', ''),
                data.get('year', ''),
                data.get('location', '')
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"插入参考文献失败: {e}")

    def insert_mechanisms_and_models(self, gene_id: int, document_id: int, data: Dict):
        """插入机制与模型信息"""
        cursor = self.conn.cursor()
        try:
            # 将列表转换为字符串
            pathways = data.get('signaling_pathways', [])
            if isinstance(pathways, list):
                pathways = '; '.join(str(p) for p in pathways)
            
            subtypes = data.get('cancer_subtype', [])
            if isinstance(subtypes, list):
                subtypes = '; '.join(str(s) for s in subtypes)
            
            models = data.get('experimental_model', [])
            if isinstance(models, list):
                models = '; '.join(str(m) for m in models)
            
            evidence = data.get('evidence_level', [])
            if isinstance(evidence, list):
                evidence = '; '.join(str(e) for e in evidence)
            
            cursor.execute('''
                INSERT OR REPLACE INTO mechanisms_and_models
                (gene_id, document_id, signaling_pathways, cancer_subtype, experimental_model, evidence_level)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                gene_id,
                document_id,
                pathways,
                subtypes,
                models,
                evidence
            ))
            self.conn.commit()
        except Exception as e:
            logger.error(f"插入机制与模型信息失败: {e}")

    def import_from_json(self, json_path: Path):
        """从单个PDF的JSON结果导入数据"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 插入文献记录
            doc_id = self.insert_document(
                pdf_file=data['pdf_file'],
                pdf_path=data['pdf_path'],
                page_count=data.get('page_count', 0),
                status=data.get('status', 'ok'),
                gene_count=data.get('gene_count', 0),
                extraction_time=data.get('extraction_time', '')
            )

            if doc_id == -1:
                logger.error(f"无法插入文献: {json_path}")
                return

            # 插入基因信息
            for gene in data.get('genes', []):
                gene_name = gene.get('gene_name', '')
                if not gene_name:
                    continue

                gene_id = self.insert_gene(
                    gene_name=gene_name,
                    gene_function_category=gene.get('basic_info', {}).get('gene_function_category', '')
                )

                if gene_id == -1:
                    logger.error(f"无法插入基因: {gene_name}")
                    continue

                # 插入表达与预后信息
                if 'expression_and_prognosis' in gene:
                    self.insert_expression_prognosis(gene_id, doc_id, gene['expression_and_prognosis'])

                # 插入靶向治疗信息
                if 'targeted_therapy' in gene:
                    self.insert_targeted_therapy(gene_id, doc_id, gene['targeted_therapy'])

                # 插入突变与表观遗传信息
                if 'mutation_and_epigenetics' in gene:
                    self.insert_mutation_epigenetics(gene_id, doc_id, gene['mutation_and_epigenetics'])

                # 插入生物学功能
                functions = gene.get('biological_functions', [])
                if functions:
                    self.insert_biological_functions(gene_id, doc_id, functions)

                # 插入机制与模型信息
                if 'mechanisms_and_models' in gene:
                    self.insert_mechanisms_and_models(gene_id, doc_id, gene['mechanisms_and_models'])

                # 插入参考文献信息
                if 'reference' in gene:
                    self.insert_reference(gene_id, doc_id, gene['reference'])

            logger.info(f"成功导入: {json_path}")

        except Exception as e:
            logger.error(f"导入JSON失败 {json_path}: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

    def import_all_from_dir(self, json_dir: Path):
        """从目录导入所有JSON文件"""
        json_files = list(json_dir.glob('*_result.json'))
        logger.info(f"找到 {len(json_files)} 个JSON结果文件")

        for json_file in json_files:
            self.import_from_json(json_file)

    def get_gene_info(self, gene_name: str) -> Optional[Dict]:
        """获取基因的综合信息（来自所有文献）"""
        cursor = self.conn.cursor()

        # 获取基因基本信息
        cursor.execute('SELECT * FROM genes WHERE gene_name = ?', (gene_name,))
        gene_row = cursor.fetchone()
        if not gene_row:
            return None

        gene_info = {
            'gene_name': gene_row[1],
            'gene_function_category': gene_row[2],
            'sources': [],
            'expression_and_prognosis': {},
            'targeted_therapy': {},
            'mutation_and_epigenetics': {},
            'biological_functions': [],
            'references': []
        }

        gene_id = gene_row[0]

        # 获取表达与预后信息（合并所有文献）
        cursor.execute('''
            SELECT ep.*, d.pdf_file FROM expression_prognosis ep
            JOIN documents d ON ep.document_id = d.id
            WHERE ep.gene_id = ?
        ''', (gene_id,))
        
        expression_levels = set()
        os_values = set()
        dfs_values = set()
        correlations = []
        locations = []

        for row in cursor.fetchall():
            if row[2]:  # expression_level
                expression_levels.add(str(row[2]))
            if row[3]:  # prognosis_os
                os_values.add(str(row[3]))
            if row[4]:  # prognosis_dfs
                dfs_values.add(str(row[4]))
            if row[5]:  # clinicopathological_correlation
                correlations.append(str(row[5]))
            if row[6]:  # location
                locations.append(f"{row[6]} ({row[7]})")

        gene_info['expression_and_prognosis'] = {
            'expression_level': '; '.join(expression_levels) if expression_levels else '未提及',
            'prognosis_correlation': {
                'OS': '; '.join(os_values) if os_values else '未提及',
                'DFS': '; '.join(dfs_values) if dfs_values else '未提及'
            },
            'clinicopathological_correlation': '; '.join(correlations) if correlations else '未提及',
            'locations': '; '.join(locations) if locations else ''
        }

        # 获取靶向治疗信息
        cursor.execute('''
            SELECT tt.*, d.pdf_file FROM targeted_therapy tt
            JOIN documents d ON tt.document_id = d.id
            WHERE tt.gene_id = ?
        ''', (gene_id,))
        
        targets = set()
        drugs = set()
        resistances = []

        for row in cursor.fetchall():
            if row[2]:
                targets.add(str(row[2]))
            if row[3]:
                drugs.add(str(row[3]))
            if row[4]:
                resistances.append(f"{row[4]} ({row[5]})")

        gene_info['targeted_therapy'] = {
            'is_potential_target': '; '.join(targets) if targets else '未提及',
            'known_drugs': '; '.join(drugs) if drugs else '未提及',
            'drug_resistance': '; '.join(resistances) if resistances else '未提及'
        }

        # 获取突变信息
        cursor.execute('''
            SELECT me.*, d.pdf_file FROM mutation_epigenetics me
            JOIN documents d ON me.document_id = d.id
            WHERE me.gene_id = ?
        ''', (gene_id,))
        
        mutation_types = set()
        frequencies = []

        for row in cursor.fetchall():
            if row[2]:
                mutation_types.add(str(row[2]))
            if row[3]:
                frequencies.append(f"{row[3]} ({row[4]})")

        gene_info['mutation_and_epigenetics'] = {
            'mutation_types': '; '.join(mutation_types) if mutation_types else '未提及',
            'mutation_frequency': '; '.join(frequencies) if frequencies else '未提及'
        }

        # 获取生物学功能
        cursor.execute('''
            SELECT bf.function_name, d.pdf_file FROM biological_functions bf
            JOIN documents d ON bf.document_id = d.id
            WHERE bf.gene_id = ?
        ''', (gene_id,))
        
        func_map = {}
        for row in cursor.fetchall():
            func = row[0]
            source = row[1]
            if func not in func_map:
                func_map[func] = []
            func_map[func].append(source)

        gene_info['biological_functions'] = [
            f"{func} (来源: {', '.join(sources)})" 
            for func, sources in func_map.items()
        ]

        # 获取机制与模型信息
        cursor.execute('''
            SELECT mm.*, d.pdf_file FROM mechanisms_and_models mm
            JOIN documents d ON mm.document_id = d.id
            WHERE mm.gene_id = ?
        ''', (gene_id,))
        
        pathways = set()
        subtypes = set()
        models = set()
        evidences = set()
        
        for row in cursor.fetchall():
            if row[2]:  # signaling_pathways
                for p in str(row[2]).split('; '):
                    if p and p not in ['未提及', '无', '暂无']:
                        pathways.add(p.strip())
            if row[3]:  # cancer_subtype
                for s in str(row[3]).split('; '):
                    if s and s not in ['未提及', '无', '暂无']:
                        subtypes.add(s.strip())
            if row[4]:  # experimental_model
                for m in str(row[4]).split('; '):
                    if m and m not in ['未提及', '无', '暂无']:
                        models.add(m.strip())
            if row[5]:  # evidence_level
                for e in str(row[5]).split('; '):
                    if e and e not in ['未提及', '无', '暂无']:
                        evidences.add(e.strip())
        
        gene_info['mechanisms_and_models'] = {
            'signaling_pathways': sorted(list(pathways)) if pathways else [],
            'cancer_subtype': sorted(list(subtypes)) if subtypes else [],
            'experimental_model': sorted(list(models)) if models else [],
            'evidence_level': sorted(list(evidences)) if evidences else []
        }

        # 获取参考文献
        cursor.execute('''
            SELECT r.*, d.pdf_file FROM gene_references r
            JOIN documents d ON r.document_id = d.id
            WHERE r.gene_id = ?
        ''', (gene_id,))
        
        for row in cursor.fetchall():
            gene_info['references'].append({
                'title': row[2] if row[2] else f"来自文献: {row[5]}",
                'year': row[3] if row[3] else '',
                'location': row[4] if row[4] else '',
                'source_pdf': row[5]
            })

        # 获取来源文献列表
        cursor.execute('''
            SELECT DISTINCT d.pdf_file, d.pdf_path FROM documents d
            JOIN expression_prognosis ep ON d.id = ep.document_id
            WHERE ep.gene_id = ?
        ''', (gene_id,))
        
        for row in cursor.fetchall():
            gene_info['sources'].append({
                'pdf_file': row[0],
                'pdf_path': row[1]
            })

        return gene_info

    def get_all_genes(self) -> List[str]:
        """获取所有基因名称"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT gene_name FROM genes ORDER BY gene_name')
        return [row[0] for row in cursor.fetchall()]

    def export_to_json(self, output_path: Path):
        """将整合后的基因信息导出为JSON"""
        all_genes = self.get_all_genes()
        result = {
            'metadata': {
                'total_genes': len(all_genes),
                'export_time': datetime.now().isoformat(),
                'database_path': str(self.db_path)
            },
            'genes': {}
        }

        for gene_name in all_genes:
            gene_info = self.get_gene_info(gene_name)
            if gene_info:
                result['genes'][gene_name] = gene_info

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"整合结果已导出到: {output_path}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()


def main():
    """主函数"""
    # 设置路径
    project_root = Path(__file__).parent
    pdf_results_dir = project_root / "output" / "pdf_results"
    db_path = project_root / "output" / "gene_info.sqlite3"
    output_json = project_root / "output" / "integrated_gene_results.json"

    # 检查JSON结果目录
    if not pdf_results_dir.exists():
        logger.error(f"PDF结果目录不存在: {pdf_results_dir}")
        logger.info("请先运行 main.py 生成PDF结果")
        return

    # 创建数据库
    db = GeneInfoDatabase(str(db_path))

    try:
        # 导入所有JSON结果
        logger.info("开始导入JSON结果到数据库...")
        db.import_all_from_dir(pdf_results_dir)

        # 导出整合后的结果
        logger.info("导出整合结果...")
        db.export_to_json(output_json)

        # 显示统计信息
        all_genes = db.get_all_genes()
        logger.info(f"数据库中共有 {len(all_genes)} 个基因")
        
        if all_genes:
            logger.info("基因列表:")
            for gene in all_genes[:10]:  # 只显示前10个
                logger.info(f"  - {gene}")
            if len(all_genes) > 10:
                logger.info(f"  ... 还有 {len(all_genes) - 10} 个基因")

    finally:
        db.close()


if __name__ == "__main__":
    main()