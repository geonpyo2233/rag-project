import json
# Langchain에서 텍스트를 다루는 기본단위
from langchain_core.documents import Document
# 청크로 잘라주는 도구
from langchain_text_splitters import RecursiveCharacterTextSplitter
# 허깅페이스의 임베딩 모델 불러오기
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
# 벡터 DB 저장
from langchain_community.vectorstores import Chroma

# 한국어에 특화된 모델 로드
embeddings = HuggingFaceBgeEmbeddings(model_name="jhgan/ko-sroberta-multitask")

# json_path pdf_extractor.py가 만든 json파일 경로
# chroma_dir 크로마 db 저장 폴더 경로
def build_vectorstore(json_path, chroma_dir):
    print(f'[파이프라인 시작] {json_path}')

    # JSON 로드해 all_page_texts에 넣기
    with open(json_path, 'r', encoding='utf-8') as f:
        all_page_texts = json.load(f)
    print(f'  로드 완료: {len(all_page_texts)}페이지')

    # json을 문서 형식으로 변환하는건데
    # 이때 본문인 content > page_content에 넣고
    # 부가적인 page와 method는 metadata에 넣어 부가 설명으로 설정
    docs = []
    for page_data in all_page_texts:
        doc = Document(
            page_content=page_data['content'],
            metadata={
                'page'  : page_data['page'],
                'method': page_data['method'],
            }
        )
        # docs에 저장
        docs.append(doc)
    print(f'  Document 변환: {len(docs)}개')

    # 청킹
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )
    # split_documents 함수로 docs를 잘라준다
    chunks = splitter.split_documents(docs)
    print(f'  청킹 완료: {len(chunks)}개')

    # chunks를 embeddings 모델로 벡터 변환
    # 변환된 벡터 chroma_dir에 저장
    Chroma.from_documents(chunks, embeddings, persist_directory=chroma_dir)
    print(f'[파이프라인 완료] Chroma 저장: {chroma_dir}')