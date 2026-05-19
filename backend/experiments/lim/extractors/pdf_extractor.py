# PDF에 텍스트만 있는 페이지 읽어서 처리하기 위해
import pdfplumber
# PDF를 이미지로 만드는 라이브러리
from pdf2image import convert_from_path
# 이미지가 된거 텍스트로 바꿔야해
from paddleocr import PaddleOCR
import json
import numpy as np

# 이미지를 읽는 PaddleOCR을 선언해주는거
ocr = PaddleOCR(use_angle_cls = True, lang='korean')

# 이미지를 OCR해서 텍스트로 바꾸는 과정
def get_text_by_ocr(image):
    image_np = np.array(image) # PIL 이미지를 OCR이 못읽으니까 numpy배열로 변환
    result = ocr.ocr(image_np, cls=True) # 실제 이미지를 OCR하는 곳

    # OCR한 결과값을 저장하기 위한 빈 리스트 준비 
    texts = []
    # result에 OCR한게 들어 있는데 이때 result에 이상한 정보?들도 들어있어 text만 뽑기 위함
    for block in result :
        # block에 None이거나 비어있음 패스
        if block:
            for line in block:
                # 텍스트만 추출
                texts.append(line[1][0])
    # 나온 값 ['안녕하세요'],['반갑습니다']와 같은 결과를
    # 하나의 문장으로 return한다
    return '\n'.join(texts)

# 실제 pdf를 받아 json파일로 저장하는 과정
def extract(pdf_path, output_path, threshold=50):
    # 추출 시작이라는 안내와 어떤 pdf를 추출하는지
    print(f'추출 시작 {pdf_path}')

    # convert_from_path로 pdf를 이미지로 변환하는데
    # 이때 선명도는 400, 색감은 흑백으로 설정한다
    images = convert_from_path(pdf_path, dpi=400, grayscale=True)

    results = []

    # pdfplumber로 pdf파일 열기
    with pdfplumber.open(pdf_path) as pdf:
        # pdf를 연 상태에서 i에 인덱스 page에 본문내용을 넣는다(pdf.pages -> 페이지 목록 꺼내기)
        for i, page in enumerate(pdf.pages):
            # page에 있는 목록에서 .extract_text하여 본문을 text에 저장
            # 현재 pdfplumber로 pdf를 열었기 때문에 이미지를 텍스트를 뽑지 못해 ""으로 오류 제거
            text = page.extract_text() or ""

            # pdf의 본문을 뽑은 내용이 threshold보다 크거나 같을 때 실행
            if len(text.strip()) >= threshold:
                method = 'text' # json파일에 저장할 때 어떤 걸 사용했는지
                content = text.strip() # 본문 내용
            else :
                method = 'ocr'
                # 위에서 준비한 get_text_by_ocr을 준비하여 
                # images에는 이미 convert_from_path로 이미지화 된걸로 돌림
                content = get_text_by_ocr(images[i])

            # pdfplumber, ocr을 돌린 결과를 저장하는 곳
            # pages는 페이지 번호
            # method는 무슨 형식으로 추출했는지
            # content 메인 본문
            results.append({
                'page' : i + 1,
                'method' : method,
                'content' : content
            })

            print(f'페이지 {i+1}완료 ({method}형식)')
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'추출완료 {output_path}에 저장')
    return output_path

