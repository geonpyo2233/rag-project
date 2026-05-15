import json
from langchain_community.llms import Ollama
 
# LLM은 한 번만 로드
llm = Ollama(model="qwen3:8b", temperature=0.3)
 
 
def run(json_path):
    # OCR 결과 JSON을 읽어 LLM으로 요약 + 카테고리 생성
    print(f'[LLM 시작] {json_path}')
 
    # JSON 로드 후 전체 텍스트 합치기
    with open(json_path, 'r', encoding='utf-8') as f:
        all_pages = json.load(f)
 
    context = '\n\n'.join([f"[{p['page']}페이지]\n{p['content']}" for p in all_pages])

    prompt = f"""당신은 참고자료 기반 문서 요약 시스템입니다.
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
    - ....

    [문서 내용]
    {context}

    [답변]
    """
    answer = llm.invoke(prompt)
    print(f'[LLM 완료]')

    # 카테고리와 요약을 파싱해서 딕셔너리로 반환
    category = ""
    summary  = ""

    for line in answer.splitlines():
        if line.startswith("카테고리 :"):
            category = line.replace("카테고리 :", "").strip()
        elif line.startswith("요약 :") or line.startswith("-"):
            summary += line + "\n"

    return {
        "category": category,
        "summary" : summary.strip(),
        "raw"     : answer  # 파싱 실패 대비 원본도 같이 반환
    }