# json 파일 읽고 쓰는 라이브러리
import json
# 허깅페이스에 있는 임베딩 모델 불러오기
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
# 벡터를 저장하고 검색할 수 있게
from langchain_community.vectorstores import Chroma
# Ollama LLM을 Langchain에서 쓸 수 있게 하기 위함
from langchain_community.llms import Ollama
# 프롬프트 템플릿을 만드는 도구 현재는 사용 안함
from langchain_core.prompts import PromptTemplate

# 경로 설정 베이스라인
base_dir = "/Users/imgeonpyo/rag-project/backend/experiments/lim"
# 벡터 를 저장한 폴더
chroma_dir = f"{base_dir}/data/chroma_db"
json_path = f"{base_dir}/data/ocr_output/ocr_documents.json"

print('준비중')
# 허깅페이스에서 한국어 임베딩 모델을 로드 
embeddings = HuggingFaceBgeEmbeddings(model_name = 'jhgan/ko-sroberta-multitask')
# rag_pipeline,py에서 저장해둔 ChromaDB를 불러온다 
# from_documents가 아니라 Chroma만 쓰는 이유가 새로 만드는게 아니기 때문
vectorstore = Chroma(persist_directory=chroma_dir, embedding_function=embeddings)
# Ollama에 실행중인 qwen3:8b연결 temperature=0.3은 창의성 수치인데, 0에 가까울수록 일관되고 안정적인 답변
llm = Ollama(model="qwen3:8b", temperature = 0.3)
print('준완\n')

# 질문을 받아 답변을 돌려주는 함수
def ask(query) :
    # Chroma DB에서 질문이랑 가장 유사한 청크 3개를 찾아온다
    all_pages = json.load(open(json_path, 'r', encoding='utf-8'))
    context = '\n\n'.join([p['text'] for p in all_pages])

    # LLM한테 보낼 최종 텍스트
    prompt = f""" 아래 문서 전체 내용을 빠짐없이 요약해줘.

    [문서 내용]
    {context}

   

    [답변]
"""
    # 완성된 프롬프트를 모델한테 던져 답변을 받아오는 코드
    # invoke는 실행 해줘라는 뜻
    answer = llm.invoke(prompt)
    return answer


while True :
    query = input('질문 : ').strip()
    if query == 'q':
        break
    print('\n'+ask(query)+'\n')