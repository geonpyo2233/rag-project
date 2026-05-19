# DOCX OCR Comparison

Sample:

- `오픈 빅데이터 방법론- 탄생배경과 1부 BAM 소개.docx`

## Files

- `baseline_paddle_docx_image_ocr.txt`
  - Current docx extractor output copied before experiments.
- `experiment_01_xml_all_text.txt`
  - Raw text nodes extracted from DOCX XML parts.
- `experiment_02_upscale_2x_rgb_ocr.txt`
  - DOCX embedded images resized 2x in RGB, then OCR.
- `experiment_03_upscale_2x_det1600_ocr.txt`
  - Same 2x RGB images, PaddleOCR `det_limit_side_len=1600`.

## Quick Read

- XML extraction is clean, but it does not recover most diagram internals.
- 2x RGB upscale reduces several obvious OCR errors:
  - `Methodolog!` -> fewer/none
  - `5elect` -> `Select`
  - `Gata` -> `Data`
  - `Patterhinc` -> fewer/none
- 2x RGB with `det_limit_side_len=1600` is not clearly better than simple 2x RGB for this sample.

## Current Best Candidate

For image OCR quality only, `experiment_02_upscale_2x_rgb_ocr.txt` looks like the best next candidate to integrate.
