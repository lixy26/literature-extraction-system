#!/usr/bin/env python3
"""下载肝癌基因相关论文"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import time
import re

# 已下载的论文ID（根据之前的记录）
existing_ids = [
    "2412.12214v1",
    "2005.04069v1", 
    "2605.20891v1",
    "1611.07588v2",
    "1604.08743v4",
    "2510.19870v1",
    "2412.03084v2",
    "1012.4726v2"
]

# 提取纯ID（去掉版本号）
def get_base_id(paper_id):
    return paper_id.split('v')[0]

existing_base_ids = [get_base_id(pid) for pid in existing_ids]

# 下载目录
download_dir = r"E:\大三下\生物信息实验\MCP肝癌文献下载"
os.makedirs(download_dir, exist_ok=True)

def search_arxiv(query, max_results=30):
    """搜索arXiv"""
    base_url = "http://export.arxiv.org/api/query?"
    params = {
        'search_query': query,
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance'
    }
    url = base_url + urllib.parse.urlencode(params)
    print(f"搜索URL: {url}")
    
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read().decode('utf-8')
        return data
    except Exception as e:
        print(f"搜索错误: {e}")
        return None

def parse_entries(xml_data):
    """解析XML获取论文信息"""
    root = ET.fromstring(xml_data)
    entries = []
    
    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
        paper_info = {}
        
        # ID
        id_url = entry.find('{http://www.w3.org/2005/Atom}id').text
        paper_info['id'] = id_url.split('/')[-1]
        
        # 标题
        title = entry.find('{http://www.w3.org/2005/Atom}title').text
        paper_info['title'] = ' '.join(title.split()) if title else "Unknown"
        
        # 摘要
        summary = entry.find('{http://www.w3.org/2005/Atom}summary').text
        paper_info['summary'] = ' '.join(summary.split())[:200] + "..." if summary else ""
        
        # 发布日期
        published = entry.find('{http://www.w3.org/2005/Atom}published').text
        paper_info['published'] = published[:10] if published else ""
        
        entries.append(paper_info)
    
    return entries

def download_paper(paper_id, title):
    """下载论文PDF"""
    base_id = get_base_id(paper_id)
    if base_id in existing_base_ids:
        print(f"跳过已下载: {paper_id}")
        return False
    
    # 清理标题用于文件名
    clean_title = re.sub(r'[^\w\s-]', '', title)[:50]
    clean_title = re.sub(r'\s+', '_', clean_title)
    
    pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
    filename = f"{paper_id}_{clean_title}.pdf"
    filepath = os.path.join(download_dir, filename)
    
    if os.path.exists(filepath):
        print(f"文件已存在: {filename}")
        return False
    
    try:
        print(f"下载: {paper_id} - {title[:50]}...")
        urllib.request.urlretrieve(pdf_url, filepath)
        print(f"保存到: {filename}")
        time.sleep(3)  # 避免请求过快
        return True
    except Exception as e:
        print(f"下载失败 {paper_id}: {e}")
        return False

# 搜索查询列表
queries = [
    "all:hepatocellular carcinoma gene",
    "all:liver cancer biomarker",
    "all:HCC gene expression",
    "all:liver cancer genomics",
    "all:hepatocellular carcinoma mutation"
]

all_entries = []
seen_ids = set()

for query in queries:
    print(f"\n{'='*60}")
    print(f"搜索: {query}")
    print('='*60)
    
    xml_data = search_arxiv(query, max_results=25)
    if xml_data:
        entries = parse_entries(xml_data)
        for entry in entries:
            base_id = get_base_id(entry['id'])
            if base_id not in seen_ids:
                seen_ids.add(base_id)
                all_entries.append(entry)
                print(f"\nID: {entry['id']}")
                print(f"标题: {entry['title'][:80]}...")
                print(f"发布: {entry['published']}")
    
    time.sleep(3)  # 避免请求过快

print(f"\n\n{'='*60}")
print(f"共找到 {len(all_entries)} 篇不重复论文")
print('='*60)

# 下载论文
downloaded = 0
for entry in all_entries:
    if download_paper(entry['id'], entry['title']):
        downloaded += 1
        if downloaded >= 15:  # 限制下载数量
            print("\n已达到下载限制")
            break

print(f"\n下载完成！共下载 {downloaded} 篇新论文")