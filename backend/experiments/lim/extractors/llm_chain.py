import json
from langchain_community.llms import Ollama

json_path = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\ocr_output\test\output.json"

print('모델 준비중...')
# Ollama에 실행중인 qwen3:8b 연결, temperature=0.3은 창의성 수치 (0에 가까울수록 일관되고 안정적인 답변)
llm = Ollama(model="qwen3:8b", temperature=0.3)
print('준비 완료\n')


def run():
    # JSON에서 모든 페이지 텍스트 읽어오기
    with open(json_path, 'r', encoding='utf-8') as f:
        all_pages = json.load(f)

    # 전체 페이지 내용을 하나의 context로 합치기
    context = '\n\n'.join([f"[{p['page']}페이지]\n{p['content']}" for p in all_pages])

    prompt = f"""
당신은 참고자료 기반 문서 요약 시스템입니다.

반드시 아래 문서 내용에 포함된 정보만 사용하세요.

금지사항:
- 참고자료에 없는 정보 추가 금지
- 법률 해석 금지
- 추론 금지
- 일반 상식 추가 금지
- 해외 사례 추가 금지
- 통계 추가 금지

문서 내용을 있는 그대로 요약하세요.

[출력 형식]

카테고리 : (한 단어 또는 짧은 구)

요약 :
- 핵심 내용
- 핵심 내용
- 핵심 내용

[문서 내용]
{context}

[답변]
"""

    # 프롬프트를 LLM에 전달하고 답변 받기
    answer = llm.invoke(prompt)
    return answer


# 실행
result = run()
print(result)