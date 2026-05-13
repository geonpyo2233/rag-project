import json
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import Chroma

base_dir   = "/Users/imgeonpyo/rag-project/backend/experiments/lim"
json_path  = f"{base_dir}/data/ocr_output/ocr_documents.json"
chroma_dir = f"{base_dir}/data/chroma_db"

with open(json_path, 'r', encoding='utf-8') as f:
    all_page_texts = json.load(f)
print(f'로드 완료: {len(all_page_texts)}페이지')

docs = []