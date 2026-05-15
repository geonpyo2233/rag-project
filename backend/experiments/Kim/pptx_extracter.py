import zipfile
import os

#HWPX 파일 추출용 라이브러리
#from hwp_extract import HWPExtractor
#from pathlib import Path

def extract_images_from_pptx(pptx_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)    

    with zipfile.ZipFile(pptx_path, 'r') as archive:
        # Look for files in the 'ppt/media' directory
        for file in archive.namelist():
            if file.startswith('ppt/media/'):
                archive.extract(file, output_folder)
                print(f"Extracted: {file}")

#extract_images_from_pptx("./test6.pptx","./pptx test6") #추출용 코드

def extract_images_from_docx(docx_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with zipfile.ZipFile(docx_path, 'r') as archive:
        # Look for files in the 'ppt/media' directory
        for file in archive.namelist():
            if file.startswith('word/media/'):
                archive.extract(file, output_folder)
                print(f"Extracted: {file}")

#extract_images_from_docx("./testb.docx","./docxb test") #추출용 코드

#아래는 HWPX용 코드이나 일단 샘플 데이터에 해당 파일 양식이 없어 주석 처리 하였습니다.
#def extract_images_from_hwpx(hwpx_path, output_folder):
#    if not os.path.exists(output_folder):
#        os.makedirs(output_folder)
#
#    with zipfile.ZipFile(hwpx_path, 'r') as archive:
#        # Look for files in the 'ppt/media' directory
#        for file in archive.namelist():
#            if file.startswith('BinData/'):
#                archive.extract(file, output_folder)
#                print(f"Extracted: {file}")

#extract_images_from_hwpx("./testc.hwpx","./hwpxc test") #추출용 코드