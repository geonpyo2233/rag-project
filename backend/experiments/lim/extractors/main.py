import json
import os
import uuid
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

from pdf_extractor import extract
from rag_pipeline import build_vectorstore
from llm_chain import run
from database import SessionLocal, 엔진, Base  # ← 여기로
from models import Category, Document           # ← 여기로

app = FastAPI()

Base.metadata.create_all(bind=엔진)

# 파일이랑 결과물 저장할 폴더
UPLOAD_DIR = "data/uploads"
JSON_DIR   = "data/ocr_output"
CHROMA_DIR = "data/chroma_db"

# 폴더 없으면 자동 생성
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(JSON_DIR,   exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    # 파일마다 고유 ID 부여 (같은 이름 파일 충돌 방지)
    file_id    = str(uuid.uuid4())
    ext        = file.filename.split(".")[-1].lower()
    file_path  = f"{UPLOAD_DIR}/{file_id}.{ext}"
    json_path  = f"{JSON_DIR}/{file_id}.json"
    chroma_dir = f"{CHROMA_DIR}/{file_id}"

    # 업로드된 파일 저장
    with open(file_path, "wb") as f:
        f.write(await file.read())
    print(f'[업로드 완료] {file.filename} → {file_path}')

    # 확장자별 추출만 다르게
    if ext == "pdf":
        extract(file_path, json_path)

    elif ext in ("hwp", "hwpx"):
        # 팀원 코드 연결 예정
        return JSONResponse(status_code=501, content={"error": "HWP 처리는 아직 미구현입니다."})

    elif ext == "docx":
        # 팀원 코드 연결 예정
        return JSONResponse(status_code=501, content={"error": "DOCX 처리는 아직 미구현입니다."})

    elif ext in ("ppt", "pptx"):
        # 팀원 코드 연결 예정
        return JSONResponse(status_code=501, content={"error": "PPT 처리는 아직 미구현입니다."})

    else:
        return JSONResponse(status_code=400, content={"error": f".{ext} 파일은 지원하지 않습니다."})

    # ↓ 추출 이후 공통 파이프라인 (파일 형식 상관없이 동일)
    build_vectorstore(json_path, chroma_dir)
    result = run(json_path)


    db = SessionLocal()
    try:
        # 카테고리 저장
        category = Category(
            main=result["main_category"],
            sub=result["sub_category"],
            extension=ext
        )
        db.add(category)
        db.flush()  # cat_id 먼저 받아오기

        with open(json_path, encoding='utf-8') as f:
            pages = json.load(f)
        full_text = '\n\n'.join([p['content'] for p in pages])


        # 문서 저장
        document = Document(
            file_name=file.filename,
            file_type=ext,
            file_size=str(os.path.getsize(file_path)),
            cat_id=category.cat_id,
            content_full=full_text,
            content_sum=result["summary"]
        )
        db.add(document)
        db.commit()
        print("[DB 저장 완료]")
    finally:
        db.close()

    return JSONResponse(content={
        "filename" : file.filename,
        "main_category" : result["main_category"],
        "summary"  : result["summary"],
        "sub_category" : result["sub_category"]
    })