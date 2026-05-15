# OCR 결과가 JSON 파일로 저장되어 있어 JSON 읽기위해
import json
# OCR로 뽑은 텍스트를 Langchain이 이해할 수 있는 형태로 변환
from langchain_core.documents import Document
# 텍스트를 청킹하기 위해 
from langchain_text_splitters import RecursiveCharacterTextSplitter
# 텍스트를 숫자 벡터로 변환하는 도구(허깅페이스에서 모델 불러오기 위함)
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
# 임베딩된 벡터를 저장하고 검색할 수 있는 DB
from langchain_community.vectorstores import Chroma
# 아마도 변경사항이 

# 매번 긴 경로를 작성하기 귀찮아 변수에 저장
# document할 파일 경로
# 벡터 DB 저장할 경로
base_dir   = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim"
json_path  = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\ocr_output\test\output.json"
chroma_dir = f"{base_dir}\data\chroma_db"

# open(json_path, 'r') -> JSON파일을 읽기 모드로 열기
# encoding='utf-8' -> 한국어 깨짐 방지
with open(json_path, 'r', encoding='utf-8') as f:
    all_page_texts = json.load(f) # JSON파일을 로드해서 리스트로 변환
print(f'로드 완료: {len(all_page_texts)}페이지') #

# Document 객체 담는 리스트
docs = []

# JSON에서 페이지 하나씩 꺼내 반복
for page_data in all_page_texts:
    doc = Document( # LangChain의 문서 객체
        page_content=page_data['content'], # 실제 텍스트 내용을 page_content에 저장
        metadata = { # 텍스트의 부가정보 page와 socurce가 있어 이거 몇페이지야? 할 때 쓰는 정보
            'source': page_data.get('source', 'security_part1_02.pdf'),  # 없으면 기본값
            'page': page_data['page'],
            'method': page_data['method'],
        }
    )
    docs.append(doc) # 페이지 하나씩 돌아가면 리스트에 넣음
print(f'Document변환 : {len(docs)}개')
print(docs[0])


splitter = RecursiveCharacterTextSplitter(
    chunk_size = 500,
    chunk_overlap = 100
)

# split_documents(docs) docs 리스트 전체를 청킹한다
chunks = splitter.split_documents(docs)
print(f'청킹 완료: {len(chunks)}개')

# 임베딩 모델 설정
embeddings = HuggingFaceBgeEmbeddings(model_name = "jhgan/ko-sroberta-multitask")
# chunk - 잘라진 텍스트, embeddings - 임베딩 모델, 저장할 폴더 경로
vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory=chroma_dir)
print(f'Chroma 저장 완료')

# 유사도 검색 질문을 정하고 similartiy_search를 통해 가장 비슷한 벡터 3청크 찾기
query = '동물을 경품으로 주는행위를 뭐라고 규정해?'
results = vectorstore.similarity_search(query, k=3)

print(f'\n=============검색결과=============')
for i, result in enumerate(results):
    print(f"\n{i+1}페이지 {result.metadata['page']}")
    print(result.page_content)