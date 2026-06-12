SYSTEM_PROMPT = """你是一个顶级的生物信息学和肿瘤学信息提取专家，擅长从复杂的医学文献中精准提取肝癌相关基因的结构化数据。

【最高指令】
1. 你的输出必须是能够被 Python `json.loads()` 直接解析的合法 JSON 字符串。
2. 绝对不要包含任何解释性文字。
3. 绝对不要使用 Markdown 代码块标记（如 ```json 和 ```）。
4. 你的回复必须直接且只能以 `{` 开始，以 `}` 结束。
"""

USER_PROMPT = """
【任务说明】
请仔细阅读提供的文献内容，精准提取与肝癌细胞相关的基因信息，并严格按照以下维度和指定的 JSON 结构进行输出。

【输出格式与类型要求】
- 如果文献中没有找到任何基因信息，请严格输出：{"genes": []}
- 严格按照以下 JSON 结构输出，必须保持字段名称和数据类型完全一致。
- 字符串类型字段（如无相关信息）：填入 "未提及"
- 列表类型字段（如无相关信息）：填入空列表 []

{
    "genes": [
        {
            "gene_name": "HGNC官方标准基因名称（如 TP53，不要用别名）",
            "basic_info": {
                "gene_function_category": "原癌基因/抑癌基因/双向功能基因/功能未明确"
            },
            "expression_and_prognosis": {
                "expression_level": "高表达/低表达/无显著差异/未提及",
                "prognosis_correlation": {
                    "OS": "正相关/负相关/无关联/未提及",
                    "DFS": "正相关/负相关/无关联/未提及"
                },
                "clinicopathological_correlation": "描述性文本或未提及"
            },
            "targeted_therapy": {
                "is_potential_target": "是/否/正在研究/未提及",
                "known_drugs": ["药物名称1", "药物名称2"], 
                "drug_resistance": "耐药相关性描述或未提及"
            },
            "mutation_and_epigenetics": {
                "mutation_types": ["点突变", "扩增", "缺失", "甲基化"], 
                "mutation_frequency": "具体频率数据，若文献中提到具体的SNP多态性位点，必须提取出准确的rs号（如 rs1682111），若无则填未提及"
            },
            "biological_functions": ["细胞增殖", "凋亡", "侵袭转移", "血管生成", "代谢重编程", "免疫逃逸", "耐药"],
            "mechanisms_and_models": {
                "signaling_pathways": ["通路名称1", "通路名称2"],
                "cancer_subtype": ["HBV相关", "HCV相关", "酒精性", "NASH相关", "胆管细胞癌"],
                "experimental_model": ["细胞系", "动物模型", "临床标本"],
                "evidence_level": ["临床研究", "动物实验", "细胞实验", "综述"]
            },
            "reference": {
                "title": "参考文献名称",
                "year": "文献发表年份",
                "location": "【必须是字符串,不能是列表】多个位置用分号连接，得出核心信息的关键证据位置（如 Fig.1C-D;p.4），极度精简，最多保留3个最核心的位置"
            }
        }
    ]
}

【提取规则】
1. 抹除预训练偏见（极度重要）：绝对禁止基于你自带的医学知识库进行联想！必须把经典基因（如 PTEN、TP53、TIGAR 等）当作全新的未知基因对待。如果文献在特定环境下（如特定基因敲除后）报道了它们表现出反常识的功能（如抑癌基因表现出促癌表型），必须忠实提取为“双向功能基因”或提取其在该环境下的真实表型。
2. 背景与实验结果严格剥离：
   - 提取 `cancer_subtype` 时，绝不允许从 Introduction（背景介绍）或患者基线特征表（Table 1）中提取。只有当文献明确对某种亚型（如 HBV相关、NASH）进行了【独立的分组对比实验】并得出特异性结论时，才能提取。否则一律填空列表 []。
   - 不要将仅仅作为伴随性突变或背景对比的基因（如为了衬托主基因而顺带提及的 TP53）作为核心基因提取。
3. 主语隔离与归属验证（防止张冠李戴）：当同一段落讨论多个基因时，提取 `signaling_pathways` 和 `biological_functions` 必须进行严格的语法主语验证。明确识别动作的发出者，绝不能将 A 基因调控的通路或导致的血管生成，错误合并到 B 基因的属性中。
4. 实验试剂与临床药物的区分：`known_drugs` 仅指用于临床治疗该基因相关肿瘤的治疗性靶向药物（如 Lenvatinib）。绝对禁止将在体外细胞/动物实验中使用的生化抑制剂、挽救试剂、化学探针（如 Baicalein, Liproxstatin 等）提取为已知药物。若无明确的临床级药物，填空列表 []。
5. 列表字段强制规范：`known_drugs`、`mutation_types`、`biological_functions`、`signaling_pathways`、`cancer_subtype`、`experimental_model`、`evidence_level` 必须严格作为 JSON 数组 (Array) 输出。若无确凿信息，必须输出空列表 `[]`，绝对禁止输出 "无"、"未提及" 等字符串。
6. 字符串占位规范：对于 `expression_level`，务必严格判断是否存在“无显著差异”的明确表述。对于所有非列表类型的字符串字段，若文献中没有提及，请统一填写 "未提及"。
7. 溯源极简原则：`reference.location` 仅保留得出该基因核心功能的 1 到 3 处关键证据位置（如 "Fig.1C-D", "p.4"），绝不可罗列所有出现页码。
8. 零幻觉底线：所见即所得。没有写在 Results 或 Discussion 结论句里的东西，哪怕推测再合理，也绝对不能提取。

【文献内容】
{{pdf_text}}
"""

def build_prompt(pdf_text: str) -> str:
    """构建完整的用户提示词，使用字符串替换避免格式化问题"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"开始构建提示词，pdf_text长度: {len(pdf_text)}")
        # 使用字符串替换而不是format，避免JSON结构中的大括号被解析为占位符
        result = USER_PROMPT.replace('{{pdf_text}}', pdf_text)
        logger.info(f"提示词构建完成，结果长度: {len(result)}")
        
        return result
    except Exception as e:
        logger.error(f"build_prompt出错: {str(e)}")
        raise