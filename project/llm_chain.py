import json
from langchain_community.llms import Ollama
from app.config import settings

# LLM은 한 번만 로드
llm = Ollama(base_url=settings.ollama_url, model=settings.ollama_model, temperature=0.3)
 
 
def run(json_path):
    # OCR 결과 JSON을 읽어 LLM으로 요약 + 카테고리 생성
    print(f'[LLM 시작] {json_path}')
 
    # JSON 로드 후 전체 텍스트 합치기
    with open(json_path, 'r', encoding='utf-8') as f:
        all_pages = json.load(f)
 
    context = '\n\n'.join([f"[{p['page']}페이지]\n{p['content']}" for p in all_pages])

    prompt = f"""당신은 전문 문서 분류 및 요약 시스템입니다.
    반드시 한국어로만 답변하세요. 문서가 영어여도 반드시 한국어로 답변하세요.
    반드시 아래 문서 내용에 포함된 정보만 사용하세요.

    금지사항:
    - 문서에 없는 정보 추가 금지
    - 법률 해석 금지
    - 추론 및 가정 금지
    - 일반 상식 추가 금지
    - 해외 사례 추가 금지
    - 통계 추가 금지

    [출력 형식 - 반드시 아래 형식만 사용, 절대 변경 금지]
    대분류 : 문서의 핵심 주제를 한 단어 또는 짧은 구로 표현 (예: 보안관리, 계약서, 네트워크, 법령)
    소분류 : 대분류보다 구체적인 세부 주제 (예: 접근제어, 임대차계약, IoT표준화)
    요약 :
    - 핵심 내용 1
    - 핵심 내용 2
    - 핵심 내용 3
    - (필요시 추가)

    주의사항:
    - 대분류와 소분류는 절대 빈 값으로 두지 마세요
    - 명시적인 카테고리가 없으면 문서 제목이나 핵심 주제를 기반으로 직접 생성하세요
    - 요약은 문서의 핵심 내용만 간결하게 bullet point로 작성하세요
    - 요약은 문서의 모든 핵심 내용을 빠짐없이 작성하세요 (최소 5개 이상)
    - 각 bullet point는 한 문장으로 작성하세요
    - 반드시 "대분류 :", "소분류 :", "요약 :" 으로 시작하는 형식만 사용하세요
    - 다른 형식, 마크다운, 영어 사용 절대 금지

    [문서 내용]
    {context}

    [답변] 반드시 아래 형식대로만 작성하세요:
    대분류 : 
    소분류 : 
    요약 :
    - 
    """
    answer = llm.invoke(prompt)
    print(f"[LLM 응답]\n{answer}")
    print(f'[LLM 완료]')

    # 카테고리와 요약을 파싱해서 딕셔너리로 반환
    main_category = ""
    sub_category  = ""
    summary       = ""

    in_summary = False

    for line in answer.splitlines():
        line = line.strip()
        line = line.replace("**", "")
        if line.startswith("대분류"):
            main_category = line.split(":", 1)[-1].strip()
        elif line.startswith("소분류"):
            sub_category = line.split(":", 1)[-1].strip()
        elif line.startswith("요약"):
            in_summary = True
        elif in_summary and line:
            # -, * 로 시작하면 그대로, 일반 문장이면 - 붙여서 저장
            if line.startswith("-") or line.startswith("*"):
                summary += "- " + line.lstrip("*- ").strip() + "\n"
            else:
                summary += "- " + line + "\n"

    return {
        "main_category": main_category,
        "summary" : summary.strip(),
        "sub_category" : sub_category    
        }
