#!/usr/bin/env python3
"""搜索并下载肝癌基因相关论文 - 使用arXiv API"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import time
import re

download_dir = r"E:\大三下\生物信息实验\MCP肝癌文献下载"
os.makedirs(download_dir, exist_ok=True)

# 已下载的论文
existing = os.listdir(download_dir)
existing_ids = [f.split('_')[0].split('v')[0] for f in existing if f.endswith('.pdf')]
print(f"已有 {len(existing_ids)} 篇论文: {existing_ids}")

def search_arxiv(query, max_results=30):
    """搜索arXiv"""
    base_url = "http://export.arxiv.org/api/query?"
    params = {'search_query': query, 'start': 0, 'max_results': max_results, 'sortBy': 'relevance'}
    url = base_url + urllib.parse.urlencode(params)
    print(f"\n搜索: {query}")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"搜索错误: {e}")
        return None

def parse_entries(xml_data):
    """解析XML"""
    root = ET.fromstring(xml_data)
    entries = []
    ns = '{http://www.w3.org/2005/Atom}'
    
    for entry in root.findall(ns + 'entry'):
        info = {}
        info['id'] = entry.find(ns + 'id').text.split('/')[-1]
        title = entry.find(ns + 'title').text
        info['title'] = ' '.join(title.split()) if title else ""
        info['published'] = entry.find(ns + 'published').text[:10]
        
        # 获取作者
        authors = []
        for author in entry.findall(ns + 'author'):
            name = author.find(ns + 'name')
            if name is not None:
                authors.append(name.text)
        info['authors'] = authors[:3]  # 只取前3个作者
        
        entries.append(info)
    
    return entries

def download_paper(paper_id, title):
    """下载论文PDF"""
    base_id = paper_id.split('v')[0]
    if base_id in existing_ids:
        print(f"  跳过已存在: {paper_id}")
        return False
    
    clean_title = re.sub(r'[^\w\s-]', '', title)[:50]
    clean_title = re.sub(r'\s+', '_', clean_title.strip())
    
    pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
    filename = f"{paper_id}_{clean_title}.pdf"
    filepath = os.path.join(download_dir, filename)
    
    if os.path.exists(filepath):
        return False
    
    try:
        print(f"  下载: {paper_id} - {title[:50]}...")
        req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as response:
            with open(filepath, 'wb') as f:
                f.write(response.read())
        print(f"  成功!")
        existing_ids.append(base_id)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"  失败: {e}")
        return False

# 搜索查询 - 多个相关主题
queries = [
    "all:hepatocellular carcinoma gene expression",
    "all:liver cancer biomarker",
    "all:HCC prognosis gene",
    "all:liver cancer genomics",
    "all:hepatocellular carcinoma deep learning"
]

all_papers = []
seen = set()

print("="*60)
print("搜索肝癌基因相关论文...")
print("="*60)

for query in queries:
    xml = search_arxiv(query, max_results=25)
    if xml:
        entries = parse_entries(xml)
        for entry in entries:
            base_id = entry['id'].split('v')[0]
            if base_id not in seen:
                seen.add(base_id)
                all_papers.append(entry)
                print(f"  找到: {entry['id']} - {entry['title'][:50]}...")
    time.sleep(3)

print(f"\n共找到 {len(all_papers)} 篇不重复论文")

# 按相关性排序下载
print("\n" + "="*60)
print("开始下载...")
print("="*60)

downloaded = 0
for paper in all_papers:
    if download_paper(paper['id'], paper['title']):
        downloaded += 1
        if downloaded >= 15:  # 限制下载数量
            print("\n已达到下载限制 (15篇)")
            break

print(f"\n{'='*60}")
print(f"下载完成!")
print(f"新下载: {downloaded} 篇")
print(f"总计: {len(os.listdir(download_dir))} 篇论文")
print(f"保存位置: {download_dir}")
print("="*60)