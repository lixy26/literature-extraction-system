#!/usr/bin/env python3
"""
LLM输出评估系统 - 人工标注UI

提供一个Web界面让标注员从PDF中抽取信息，输出与LLM完全一致格式的JSON
支持一篇文章中存在多个基因的情况
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
from pathlib import Path
import json
import uuid
from datetime import datetime
from schema import GeneAnnotation, Reference, FIELD_DEFINITIONS

app = Flask(__name__)

# 配置
ANNOTATION_DIR = Path(__file__).parent / "annotations"
LLM_OUTPUT_DIR = Path(__file__).parent.parent / "output" / "pdf_results"
PDF_DIR = Path(__file__).parent.parent / "pdfs"

# 创建目录
ANNOTATION_DIR.mkdir(exist_ok=True)

# 获取所有PDF文件
def get_pdf_files():
    pdf_files = []
    if PDF_DIR.exists():
        for pdf in PDF_DIR.glob("*.pdf"):
            pdf_files.append(pdf.name)
    return sorted(pdf_files)

# 获取所有已有的标注文件
def get_annotations():
    annotations = []
    if ANNOTATION_DIR.exists():
        for ann_file in ANNOTATION_DIR.glob("*_annotation.json"):
            try:
                with open(ann_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 支持单基因和多基因标注
                    if "genes" in data:
                        # 多基因标注
                        gene_names = [g.get("gene_name", "Unknown") for g in data.get("genes", [])]
                        gene_name = ", ".join(gene_names) if gene_names else "Unknown"
                        pdf_file = data.get("pdf_file", "")
                    else:
                        # 单基因标注（旧格式）
                        gene_name = data.get("gene_name", "Unknown")
                        pdf_file = data.get("sources", [{}])[0].get("pdf_file", "")
                    
                    annotations.append({
                        "filename": ann_file.name,
                        "gene_name": gene_name,
                        "pdf_file": pdf_file,
                        "created_at": ann_file.stat().st_mtime
                    })
            except:
                pass
    return sorted(annotations, key=lambda x: x["created_at"], reverse=True)

# 获取LLM输出（按PDF分组）
def get_llm_outputs_by_pdf():
    outputs = {}
    if LLM_OUTPUT_DIR.exists():
        for json_file in LLM_OUTPUT_DIR.glob("*_result.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    pdf_file = data.get("pdf_file", "")
                    if pdf_file:
                        outputs[pdf_file] = {
                            "gene_count": data.get("gene_count", 0),
                            "genes": data.get("genes", []),
                            "pdf_file": pdf_file
                        }
            except:
                pass
    return outputs

@app.route('/')
def index():
    pdf_files = get_pdf_files()
    annotations = get_annotations()
    llm_outputs = get_llm_outputs_by_pdf()
    
    return render_template('index.html', 
                           pdf_files=pdf_files,
                           annotations=annotations,
                           llm_outputs=llm_outputs,
                           field_definitions=FIELD_DEFINITIONS)

@app.route('/api/llm_output_by_pdf/<pdf_name>')
def get_llm_output_by_pdf(pdf_name):
    """获取指定PDF的LLM输出（包含所有基因）"""
    llm_outputs = get_llm_outputs_by_pdf()
    if pdf_name in llm_outputs:
        return jsonify(llm_outputs[pdf_name])
    return jsonify({"genes": [], "gene_count": 0})

@app.route('/api/save_annotation', methods=['POST'])
def save_annotation():
    """保存标注数据（支持多基因）"""
    try:
        data = request.json
        
        pdf_file = data.get("pdf_file", "").strip()
        if not pdf_file:
            return jsonify({"success": False, "message": "请选择来源PDF"})
        
        # 获取所有基因数据
        genes_data = data.get("genes", [])
        if not genes_data:
            return jsonify({"success": False, "message": "请至少添加一个基因"})
        
        # 构建标注数据（与LLM输出格式一致）
        annotation_data = {
            "pdf_file": pdf_file,
            "pdf_path": str(PDF_DIR / pdf_file),
            "gene_count": len(genes_data),
            "genes": []
        }
        
        for gene_data in genes_data:
            gene_info = {
                "gene_name": gene_data.get("gene_name", "").strip(),
                "basic_info": {
                    "gene_function_category": gene_data.get("gene_function_category", "")
                },
                "expression_and_prognosis": {
                    "expression_level": gene_data.get("expression_level", ""),
                    "prognosis_correlation": {
                        "OS": gene_data.get("prognosis_os", ""),
                        "DFS": gene_data.get("prognosis_dfs", "")
                    },
                    "clinicopathological_correlation": gene_data.get("clinicopathological_correlation", "")
                },
                "targeted_therapy": {
                    "is_potential_target": gene_data.get("is_potential_target", ""),
                    "known_drugs": [d.strip() for d in gene_data.get("known_drugs", "").split(";") if d.strip()],
                    "drug_resistance": gene_data.get("drug_resistance", "")
                },
                "mutation_and_epigenetics": {
                    "mutation_types": [m.strip() for m in gene_data.get("mutation_types", "").split(";") if m.strip()],
                    "mutation_frequency": gene_data.get("mutation_frequency", "")
                },
                "mechanisms_and_models": {
                    "signaling_pathways": [p.strip() for p in gene_data.get("signaling_pathways", "").split(";") if p.strip()],
                    "cancer_subtype": [s.strip() for s in gene_data.get("cancer_subtype", "").split(";") if s.strip()],
                    "experimental_model": [m.strip() for m in gene_data.get("experimental_model", "").split(";") if m.strip()],
                    "evidence_level": [e.strip() for e in gene_data.get("evidence_level", "").split(";") if e.strip()]
                },
                "biological_functions": [f.strip() for f in gene_data.get("biological_functions", "").split(";") if f.strip()],
                "reference": {
                    "title": gene_data.get("reference_title", ""),
                    "year": gene_data.get("reference_year", ""),
                    "location": gene_data.get("location_reference", ""),
                    "pdf_file": pdf_file
                },
                "source_pdf": pdf_file
            }
            annotation_data["genes"].append(gene_info)
        
        # 生成文件名（基于PDF名称）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_base = pdf_file.replace(".pdf", "")
        filename = f"{pdf_base}_{timestamp}_annotation.json"
        filepath = ANNOTATION_DIR / filename
        
        # 保存文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(annotation_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True,
            "message": f"标注保存成功！共 {len(genes_data)} 个基因",
            "filename": filename
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"保存失败: {str(e)}"
        })

@app.route('/annotations/<filename>')
def download_annotation(filename):
    """下载标注文件"""
    return send_from_directory(ANNOTATION_DIR, filename)

@app.route('/api/delete_annotation/<filename>')
def delete_annotation(filename):
    """删除标注文件"""
    try:
        filepath = ANNOTATION_DIR / filename
        if filepath.exists():
            filepath.unlink()
            return jsonify({"success": True, "message": "删除成功"})
        return jsonify({"success": False, "message": "文件不存在"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
