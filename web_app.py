#!/usr/bin/env python3
"""
肝癌基因相关文献知识查询数据库 - Web可视化应用
仅从SQLite数据库读取数据
"""

import sqlite3
import subprocess
import logging
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 增加到100MB
app.config['UPLOAD_FOLDER'] = Path(__file__).parent / 'pdfs'
app.config['DB_FILE'] = Path(__file__).parent / 'output' / 'gene_info.sqlite3'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = sqlite3.connect(str(app.config['DB_FILE']))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"连接数据库失败: {e}")
        return None

def get_stats():
    """从数据库获取统计数据"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM documents')
            total_papers = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM genes')
            total_genes = cursor.fetchone()[0]
            conn.close()
            return {'total_papers': total_papers, 'total_genes': total_genes}
        except Exception as e:
            logger.error(f"从数据库获取统计数据失败: {e}")
            conn.close()
    return {'total_papers': 0, 'total_genes': 0}

def load_gene_data():
    """从数据库加载基因数据"""
    conn = get_db_connection()
    if not conn:
        return {'metadata': {}, 'genes': {}}
    
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM genes')
        genes_data = {}
        
        for gene_row in cursor.fetchall():
            gene_id = gene_row['id']
            gene_name = gene_row['gene_name']
            
            gene_info = {
                'gene_name': gene_name,
                'basic_info': {
                    'gene_function_category': gene_row['gene_function_category'] or '未提及'
                },
                'sources': [],
                'expression_and_prognosis': {},
                'targeted_therapy': {},
                'mutation_and_epigenetics': {},
                'biological_functions': [],
                'references': []
            }
            
            # 获取表达与预后信息
            cursor.execute('''
                SELECT ep.*, d.pdf_file FROM expression_prognosis ep
                JOIN documents d ON ep.document_id = d.id
                WHERE ep.gene_id = ?
            ''', (gene_id,))
            
            expression_levels = []
            os_values = []
            dfs_values = []
            correlations = []
            locations = []
            sources = set()
            
            for row in cursor.fetchall():
                sources.add(row['pdf_file'])
                # 过滤掉"未提及"、"无"、"暂无"等空值，并去重
                if row['expression_level'] and row['expression_level'] not in ['未提及', '无', '暂无']:
                    if row['expression_level'] not in expression_levels:
                        expression_levels.append(row['expression_level'])
                if row['prognosis_os'] and row['prognosis_os'] not in ['未提及', '无', '暂无']:
                    if row['prognosis_os'] not in os_values:
                        os_values.append(row['prognosis_os'])
                if row['prognosis_dfs'] and row['prognosis_dfs'] not in ['未提及', '无', '暂无']:
                    if row['prognosis_dfs'] not in dfs_values:
                        dfs_values.append(row['prognosis_dfs'])
                if row['clinicopathological_correlation'] and row['clinicopathological_correlation'] not in ['未提及', '无', '暂无']:
                    correlations.append(row['clinicopathological_correlation'])
                if row['location']:
                    locations.append(f"{row['location']} ({row['pdf_file']})")
            
            gene_info['expression_and_prognosis'] = {
                'expression_level': '; '.join(expression_levels) if expression_levels else '未提及',
                'prognosis_correlation': {
                    'OS': '; '.join(os_values) if os_values else '未提及',
                    'DFS': '; '.join(dfs_values) if dfs_values else '未提及'
                },
                'clinicopathological_correlation': '; '.join(correlations) if correlations else '未提及',
                'locations': '; '.join(locations) if locations else ''
            }
            
            gene_info['sources'] = [{'pdf_file': s} for s in sources]
            
            # 获取靶向治疗信息
            cursor.execute('''
                SELECT tt.* FROM targeted_therapy tt
                WHERE tt.gene_id = ?
            ''', (gene_id,))
            
            targets = []
            drugs = []
            resistances = []
            
            for row in cursor.fetchall():
                # 过滤掉"未提及"、"无"、"暂无"等空值，并去重
                if row['is_potential_target'] and row['is_potential_target'] not in ['未提及', '无', '暂无']:
                    if row['is_potential_target'] not in targets:
                        targets.append(row['is_potential_target'])
                if row['known_drugs'] and row['known_drugs'] not in ['未提及', '无', '暂无']:
                    # 处理已知药物，可能包含多个药物（分号分隔）
                    for drug in str(row['known_drugs']).split(';'):
                        drug = drug.strip()
                        if drug and drug not in drugs:
                            drugs.append(drug)
                if row['drug_resistance'] and row['drug_resistance'] not in ['未提及', '无', '暂无']:
                    if row['drug_resistance'] not in resistances:
                        resistances.append(row['drug_resistance'])
            
            gene_info['targeted_therapy'] = {
                'is_potential_target': '; '.join(targets) if targets else '未提及',
                'known_drugs': drugs if drugs else [],
                'drug_resistance': '; '.join(resistances) if resistances else '未提及'
            }
            
            # 获取突变信息
            cursor.execute('''
                SELECT me.* FROM mutation_epigenetics me
                WHERE me.gene_id = ?
            ''', (gene_id,))
            
            mutation_types = []
            frequencies = []
            
            # 收集所有来源的数据
            all_types = []
            all_freqs = []
            
            for row in cursor.fetchall():
                # 收集突变类型
                if row['mutation_types']:
                    raw_types = str(row['mutation_types']).split(';')
                    for m_type in raw_types:
                        m_type = m_type.strip()
                        if m_type and m_type not in ['未提及', '无', '暂无'] and not m_type.startswith('未提及'):
                            all_types.append(m_type)
                # 收集突变频率/rs号
                if row['mutation_frequency']:
                    freq = row['mutation_frequency'].strip()
                    if freq and freq not in ['未提及', '无', '暂无'] and not freq.startswith('未提及'):
                        all_freqs.append(freq)
            
            # 合并rs号信息到突变类型，只保留一个最佳结果
            best_type = None
            has_specific_rs = False
            
            for m_type in all_types:
                # 如果已经包含rs号，检查是否是具体的rs号
                if 'rs' in m_type:
                    # 如果已经有具体rs号，保留；否则替换为更具体的
                    if m_type.startswith('点突变(rs') and not m_type.startswith('点突变(rs号'):
                        best_type = m_type
                        has_specific_rs = True
                    elif not has_specific_rs:
                        best_type = m_type
                else:
                    # 没有rs号的类型
                    if not best_type:
                        best_type = m_type
            
            # 如果有最佳类型，检查是否需要合并rs号
            if best_type and 'rs' not in best_type:
                # 尝试找到对应的rs号并合并
                for freq in all_freqs:
                    if freq.startswith('rs') and len(freq) <= 15:
                        # 优先选择具体的rs号，而不是"rs号未在文献中提及"
                        if not freq.startswith('rs号'):
                            best_type = f"{best_type}({freq})"
                            break
                        elif not has_specific_rs:
                            best_type = f"{best_type}({freq})"
            
            if best_type:
                mutation_types.append(best_type)
            
            # 处理剩余的频率信息（非rs号的）
            for freq in all_freqs:
                if not freq.startswith('rs') or len(freq) > 15:
                    frequencies.append(freq)
            
            gene_info['mutation_and_epigenetics'] = {
                'mutation_types': mutation_types if mutation_types else [],
                'mutation_frequency': frequencies if frequencies else []
            }
            
            # 获取生物学功能（去重）
            cursor.execute('''
                SELECT DISTINCT bf.function_name FROM biological_functions bf
                WHERE bf.gene_id = ?
            ''', (gene_id,))
            
            functions = [row['function_name'] for row in cursor.fetchall()]
            gene_info['biological_functions'] = functions
            
            # 获取机制与模型信息
            cursor.execute('''
                SELECT mm.* FROM mechanisms_and_models mm
                WHERE mm.gene_id = ?
            ''', (gene_id,))
            
            pathways = set()
            subtypes = set()
            models = set()
            evidences = set()
            
            for row in cursor.fetchall():
                if row['signaling_pathways']:
                    for p in str(row['signaling_pathways']).split('; '):
                        if p and p not in ['未提及', '无', '暂无']:
                            pathways.add(p.strip())
                if row['cancer_subtype']:
                    for s in str(row['cancer_subtype']).split('; '):
                        if s and s not in ['未提及', '无', '暂无']:
                            subtypes.add(s.strip())
                if row['experimental_model']:
                    for m in str(row['experimental_model']).split('; '):
                        if m and m not in ['未提及', '无', '暂无'] and '未提及' not in m:
                            models.add(m.strip())
                if row['evidence_level']:
                    for e in str(row['evidence_level']).split('; '):
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
                SELECT gr.*, d.pdf_file FROM gene_references gr
                JOIN documents d ON gr.document_id = d.id
                WHERE gr.gene_id = ?
            ''', (gene_id,))
            
            for row in cursor.fetchall():
                gene_info['references'].append({
                    'title': row['title'] if row['title'] else f"来自文献: {row['pdf_file']}",
                    'year': row['year'] if row['year'] else '',
                    'location': row['location'] if row['location'] else '',
                    'source_pdf': row['pdf_file']
                })
            
            genes_data[gene_name] = gene_info
        
        conn.close()
        return {'metadata': {}, 'genes': genes_data}
    
    except Exception as e:
        logger.error(f"从数据库加载基因数据失败: {e}")
        conn.close()
        return {'metadata': {}, 'genes': {}}

def get_all_genes():
    """获取所有基因名称列表"""
    data = load_gene_data()
    genes = data.get('genes', {})
    gene_names = [info.get('gene_name', key) for key, info in genes.items() if info.get('gene_name', key) != 'unknown']
    return sorted(set(gene_names))

def get_unique_list_values(main_key, sub_key):
    """通用抽取函数：用于获取嵌套数据中的去重列表"""
    data = load_gene_data()
    unique_set = set()
    for gene_info in data.get('genes', {}).values():
        section = gene_info.get(main_key, {})
        items = section.get(sub_key, [])
        if isinstance(items, list):
            for item in items:
                item = str(item).strip()
                if item and len(item) > 1 and item not in ['无', '暂无', '未知', '尚不明确', '未提及']:
                    unique_set.add(item)
    return sorted(list(unique_set))

def get_year_range():
    """获取年份范围"""
    data = load_gene_data()
    years = []
    for gene_info in data.get('genes', {}).values():
        # 从references字段获取年份
        for ref in gene_info.get('references', []):
            year = ref.get('year', '')
            if year:
                try:
                    years.append(int(year))
                except:
                    pass
    return (min(years), max(years)) if years else (2000, 2026)

def run_main_processor():
    """运行main.py重新处理PDF"""
    try:
        main_py = Path(__file__).parent / 'main.py'
        result = subprocess.run(['python', str(main_py)], capture_output=True, text=True, timeout=600)
        logger.info(f"main.py输出: {result.stdout}")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"运行main.py出错: {e}")
        return False

def run_db_integration():
    """运行json_to_sql.py整合数据到数据库"""
    try:
        json_to_sql_py = Path(__file__).parent / 'json_to_sql.py'
        result = subprocess.run(['python', str(json_to_sql_py)], capture_output=True, text=True, timeout=600)
        logger.info(f"json_to_sql.py输出: {result.stdout}")
        if result.stderr:
            logger.error(f"json_to_sql.py错误: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"运行json_to_sql.py出错: {e}")
        return False

@app.route('/')
def index():
    stats = get_stats()
    year_min, year_max = get_year_range()
    
    return render_template('index.html',
                           stats=stats,
                           all_genes=get_all_genes(),
                           all_drugs=get_unique_list_values('targeted_therapy', 'known_drugs'),
                           all_pathways=get_unique_list_values('mechanisms_and_models', 'signaling_pathways'),
                           all_subtypes=get_unique_list_values('mechanisms_and_models', 'cancer_subtype'),
                           all_models=get_unique_list_values('mechanisms_and_models', 'experimental_model'),
                           year_min=year_min,
                           year_max=year_max)

@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())

@app.route('/api/genes')
def api_genes():
    data = load_gene_data()
    genes = data.get('genes', {})
    filters = request.args
    filtered_genes = {}

    for gene_key, gene_info in genes.items():
        gene_name = gene_info.get('gene_name', gene_key)
        include = True

        if filters.get('gene_name') and filters['gene_name'].lower() not in gene_name.lower():
            include = False

        if filters.get('category'):
            category = gene_info.get('basic_info', {}).get('gene_function_category', '')
            if filters['category'] not in category:
                include = False

        if filters.get('drug'):
            known_drugs = gene_info.get('targeted_therapy', {}).get('known_drugs', [])
            if not isinstance(known_drugs, list) or not any(filters['drug'].lower() in d.lower() for d in known_drugs):
                include = False

        if filters.get('pathway'):
            pathways = gene_info.get('mechanisms_and_models', {}).get('signaling_pathways', [])
            if not isinstance(pathways, list) or not any(filters['pathway'].lower() in p.lower() for p in pathways):
                include = False

        try:
            ref_year = 0
            for ref in gene_info.get('references', []):
                year = ref.get('year', '')
                if year:
                    try:
                        ref_year = int(year)
                        break
                    except:
                        pass
            if filters.get('year_from') and ref_year < int(filters['year_from']):
                include = False
            if filters.get('year_to') and ref_year > int(filters['year_to']):
                include = False
        except:
            pass

        if include:
            filtered_genes[gene_name] = gene_info

    return jsonify(filtered_genes)

@app.route('/api/gene/<gene_name>/details')
def api_gene_details(gene_name):
    """获取特定基因的详细文献信息"""
    # 从JSON文件读取原始数据
    pdf_results_dir = Path(__file__).parent / 'output' / 'pdf_results'
    gene_details = []
    
    # 获取该基因在数据库中关联的文档
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': '无法连接数据库'})
    
    try:
        cursor = conn.cursor()
        # 查询该基因关联的所有文档ID
        cursor.execute('''
            SELECT DISTINCT d.id, d.pdf_file
            FROM documents d
            JOIN expression_prognosis ep ON d.id = ep.document_id
            JOIN genes g ON ep.gene_id = g.id
            WHERE g.gene_name = ?
            UNION
            SELECT DISTINCT d.id, d.pdf_file
            FROM documents d
            JOIN targeted_therapy tt ON d.id = tt.document_id
            JOIN genes g ON tt.gene_id = g.id
            WHERE g.gene_name = ?
            UNION
            SELECT DISTINCT d.id, d.pdf_file
            FROM documents d
            JOIN mutation_epigenetics me ON d.id = me.document_id
            JOIN genes g ON me.gene_id = g.id
            WHERE g.gene_name = ?
            UNION
            SELECT DISTINCT d.id, d.pdf_file
            FROM documents d
            JOIN mechanisms_and_models mm ON d.id = mm.document_id
            JOIN genes g ON mm.gene_id = g.id
            WHERE g.gene_name = ?
            UNION
            SELECT DISTINCT d.id, d.pdf_file
            FROM documents d
            JOIN biological_functions bf ON d.id = bf.document_id
            JOIN genes g ON bf.gene_id = g.id
            WHERE g.gene_name = ?
        ''', (gene_name, gene_name, gene_name, gene_name, gene_name))
        
        documents = cursor.fetchall()
        
        for doc in documents:
            doc_id = doc['id']
            pdf_file = doc['pdf_file']
            
            # 查找对应的JSON文件
            json_file = None
            if pdf_file:
                # 从pdf文件名构建json文件名（去掉.pdf后缀）
                json_name = pdf_file.replace('.pdf', '') + '_result.json'
                json_file = pdf_results_dir / json_name
            
            if json_file and json_file.exists():
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 在genes列表中查找该基因
                        for gene in data.get('genes', []):
                            if gene.get('gene_name') == gene_name:
                                ref = gene.get('reference', {})
                                gene_details.append({
                                    'document_id': doc_id,
                                    'pdf_file': pdf_file,
                                    'title': ref.get('title', '') if isinstance(ref, dict) else '',
                                    'authors': gene.get('authors', ''),
                                    'year': str(ref.get('year', '')) if isinstance(ref, dict) else '',
                                    'gene_data': gene
                                })
                                break
                except Exception as e:
                    logger.error(f"读取JSON文件失败: {json_file}, 错误: {e}")
            else:
                # 如果找不到JSON文件，返回基本信息
                gene_details.append({
                    'document_id': doc_id,
                    'pdf_file': pdf_file,
                    'title': '',
                    'authors': '',
                    'year': '',
                    'gene_data': None
                })
        
        conn.close()
        return jsonify({
            'success': True,
            'gene_name': gene_name,
            'documents': gene_details
        })
        
    except Exception as e:
        logger.error(f"获取基因详情失败: {e}")
        conn.close()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': '没有文件上传'})
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    uploaded_count = 0
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = app.config['UPLOAD_FOLDER'] / filename
            file.save(save_path)
            uploaded_count += 1
    
    if uploaded_count == 0:
        return jsonify({'success': False, 'message': '没有有效的PDF文件'})
    
    return jsonify({'success': True, 'message': f'成功上传 {uploaded_count} 个文件，正在重新处理...'})

@app.route('/api/process', methods=['POST'])
def process_pdfs():
    # 先运行main.py处理PDF
    if not run_main_processor():
        return jsonify({'success': False, 'message': '处理PDF失败'})
    
    # 再运行json_to_sql.py整合到数据库
    if not run_db_integration():
        return jsonify({'success': False, 'message': '整合数据到数据库失败'})
    
    stats = get_stats()
    return jsonify({'success': True, 'message': '处理完成', 'stats': stats})

@app.route('/refresh')
def refresh_page():
    return redirect(url_for('index'))

@app.route('/pdfs/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
