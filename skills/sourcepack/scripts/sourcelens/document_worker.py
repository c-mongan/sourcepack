"""Optional converter process. Import no optional package in the core process."""
import json
from pathlib import Path
import re
import socket
import sys

def deny_network(*args,**kwargs):raise RuntimeError('Document worker network access disabled')

def convert(request):
    # Defense in depth for Python HTTP clients and external image relationships.
    # Qualification still checks actual offline behavior; this is not an OS sandbox.
    socket.create_connection=deny_network
    socket.socket.connect=deny_network
    source=Path(request['source']);out=Path(request['output']);assets=[];gaps=[]
    if request['profile']=='documents-basic':
        from markitdown import MarkItDown
        from importlib.metadata import version
        if source.suffix=='.pdf':
            from pdfminer.pdfpage import PDFPage
            with source.open('rb') as f:
                for n,page in enumerate(PDFPage.get_pages(f,check_extractable=True),1):
                    if n>200:raise ValueError('PDF exceeds 200 page budget')
        result=MarkItDown(enable_plugins=False).convert_local(str(source))
        markdown=result.text_content;blocks=[];locator={'coordinate_basis':'derived-section','section':1}
        for n,part in enumerate(re.split(r'\n\s*\n',markdown),1):
            slide=re.search(r'<!-- Slide number: (\d+) -->',part)
            if slide:locator={'coordinate_basis':'producer-slide-marker','slide':int(slide.group(1))}
            elif source.suffix=='.xlsx' and part.startswith('## '):locator={'coordinate_basis':'producer-sheet-heading','sheet':part.splitlines()[0][3:].strip()}
            elif source.suffix not in ('.xlsx','.pptx'):locator={'coordinate_basis':'derived-section','section':n}
            if part.strip():blocks.append({'text':part,'locator':dict(locator)})
        gaps=['Derived Markdown; text extraction does not establish visual coverage. No page coordinates invented.']
        if source.suffix!='.pdf':gaps.append('Office page count not available; byte/archive/time/block budgets applied.')
        producer_version=version('markitdown')
    else:
        # Never construct Docling until artifacts have been checked by the parent.
        if not request.get('artifacts_path') or not request.get('artifacts_manifest'):raise ValueError('Layout artifacts required')
        from docling.document_converter import DocumentConverter,PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from importlib.metadata import version
        opts=PdfPipelineOptions(artifacts_path=Path(request['artifacts_path']),enable_remote_services=False,allow_external_plugins=False,do_ocr=False,generate_page_images=True)
        converter=DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(pipeline_options=opts)})
        result=converter.convert(source,max_num_pages=200,max_file_size=64*1024*1024)
        doc=result.document;markdown=doc.export_to_markdown();native=out/'docling.json'
        native.write_text(json.dumps(doc.export_to_dict(),ensure_ascii=False))
        assets.append({'path':'docling.json','locator':{'coordinate_basis':'native-docling'}});blocks=[]
        for item,level in doc.iterate_items():
            text=getattr(item,'text',None)
            if text is None and hasattr(item,'export_to_markdown'):text=item.export_to_markdown(doc=doc)
            if not text:continue
            provenance=[{'page':p.page_no,'bbox':p.bbox.model_dump(mode='json')} for p in item.prov]
            blocks.append({'text':text,'locator':{'coordinate_basis':'docling-native','item_ref':item.self_ref,'provenance':provenance}})
        for page_no,page in doc.pages.items():
            if page.image:
                filename=f'page-{page_no}.png';page.image.pil_image.save(out/filename)
                assets.append({'path':filename,'locator':{'coordinate_basis':'docling-page','page':page_no}})
        gaps=['OCR disabled; scanned content may be incomplete. Native page images require host visual inspection.']
        producer_version=version('docling-slim')
    (out/'producer.json').write_text(json.dumps({'version':producer_version,'markdown':markdown,'blocks':blocks,'assets':assets,'gaps':gaps},ensure_ascii=False))

if __name__=='__main__':
    convert(json.loads(Path(sys.argv[1]).read_text()))
