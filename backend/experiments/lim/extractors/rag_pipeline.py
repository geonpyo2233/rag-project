import json
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import Chroma

# 임베딩 모델은 한 번만 로드
embeddings = HuggingFaceBgeEmbeddings(model_name="jhgan/ko-sroberta-multitask")


def build_vectorstore(json_path, chroma_dir):
    # OCR 결과 JSON을 읽어 청킹 → 임베딩 → Chroma DB 저장
    print(f'[파이프라인 시작] {json_path}')

    # JSON 로드
    with open(json_path, 'r', encoding='utf-8') as f:
        all_page_texts = json.load(f)
    print(f'  로드 완료: {len(all_page_texts)}페이지')

    # Document 변환
    docs = []
    for page_data in all_page_texts:
        doc = Document(
            page_content=page_data['content'],
            metadata={
                'page'  : page_data['page'],
                'method': page_data['method'],
            }
        )
        docs.append(doc)
    print(f'  Document 변환: {len(docs)}개')

    # 청킹
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )
    chunks = splitter.split_documents(docs)
    print(f'  청킹 완료: {len(chunks)}개')

    # 임베딩 + Chroma 저장
    Chroma.from_documents(chunks, embeddings, persist_directory=chroma_dir)
    print(f'[파이프라인 완료] Chroma 저장: {chroma_dir}')