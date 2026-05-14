#%% Convert PowerPoint PPT to PDF

# Purpose: Converts a PowerPoint file (PPT) to Adobe PDF

# 원래 Author:  Matthew Renze

# Usage:   python.exe Convert.py input-file output-file
#   - input-file = the PowerPoint file to be converted
#   - output-file = the Adobe PDF to be created

# Example: python.exe Convert.py C:\InputFile.pptx C:\OutputFile.pdf

# Note: Also works with PPTX file format

#%% Import libraries
import sys
import os
import comtypes.client

#OCR 가동 파일 추가 import 필요

#%% 하기 코드들은 콘솔 가동시 테스트 용 arg 필요합니다

#%% Get console arguments
input_file_path = sys.argv[1]
output_file_path = sys.argv[2]

#%% Convert file paths to Windows format
input_file_path = os.path.abspath(input_file_path)
output_file_path = os.path.abspath(output_file_path)

#%% Create powerpoint application object
powerpoint = comtypes.client.CreateObject("Powerpoint.Application")

#%% Set visibility to minimize
powerpoint.Visible = 1

#%% Open the powerpoint slides
slides = powerpoint.Presentations.Open(input_file_path)

#%% Save as PDF (formatType = 32)
slides.SaveAs(output_file_path, 32)

#%% Close the slide deck
slides.Close()
powerpoint.Quit()

##def 본문 시작

def convert_ppt_to_pdf(input_ppt):
    powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
    powerpoint.Visible = 1
    presentation = powerpoint.Presentations.Open(os.path.abspath(input_ppt))
    ##pdf 변환
    presentation.SaveAs(os.path.abspath(input_ppt), 32) # 32 = PDF
    #%%작업 후 파워포인트 닫기
    presentation.Close()
    powerpoint.Quit()

    #다음 PDF OCR 인식기 가동 추가
    ## pdfOCR(output_file_path)
