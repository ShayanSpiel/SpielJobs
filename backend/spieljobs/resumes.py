"""Bounded text extraction; uploaded files never enter persistent storage."""
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree

from pypdf import PdfReader


def extract_resume(data):
    if len(data) > 2_000_000:
        raise ValueError('Resume must be under 2 MB')
    if data.startswith(b'%PDF-'):
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > 20:
            raise ValueError('PDF must have at most 20 pages')
        text = '\n'.join(page.extract_text() or '' for page in reader.pages)[:30000]
    elif data.startswith(b'PK'):
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 128 or sum(item.file_size for item in entries) > 8_000_000:
                raise ValueError('DOCX expands beyond the safe size limit')
            if 'word/document.xml' not in archive.namelist():
                raise ValueError('Please upload a PDF or DOCX')
            xml = archive.read('word/document.xml')
            if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                raise ValueError('Unsupported DOCX XML')
            root = ElementTree.fromstring(xml)
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p', ns))[:30000]
    else:
        raise ValueError('Please upload a PDF or DOCX')
    if not text.strip():
        raise ValueError('No text found. Scanned resumes are not supported.')
    return text
