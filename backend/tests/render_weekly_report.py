"""Render the weekly PDF for visual inspection."""
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image, ImageOps
from pypdf import PdfReader

root = Path(__file__).resolve().parents[2]
path = root / 'output/pdf/aniro-weekly-2026-10-26.pdf'
destination = root / 'tmp/pdfs'
destination.mkdir(parents=True, exist_ok=True)
pdf = pdfium.PdfDocument(path)
images=[]
for index, page in enumerate(pdf):
    image = page.render(scale=1.3).to_pil().convert('RGB')
    image.save(destination / f'weekly-page-{index+1}.png')
    image.thumbnail((390,550))
    images.append(image)
montage = Image.new('RGB', (410*len(images),570), '#dce1d7')
for index,image in enumerate(images):
    montage.paste(image,(index*410+10,10))
montage.save(destination / 'weekly-review.png')
reader=PdfReader(path)
for index,page in enumerate(reader.pages):
    print(index+1, len(page.extract_text()), page.extract_text()[:90].replace('\n',' / '))
