"""Bounded, read-only extraction for user-selected chat documents. No agent run."""
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 16_000
MAX_EXPANDED_BYTES = 20 * 1024 * 1024
TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.xml', '.dbc', '.arxml', '.ldf', '.asc', '.log', '.yaml', '.yml'}


def extract_document(filename: str, content: bytes) -> dict:
    name = PurePosixPath(filename.replace('\\', '/')).name[:180]
    suffix = PurePosixPath(name).suffix.lower()
    if not content:
        raise ValueError('Die Datei ist leer.')
    if len(content) > MAX_FILE_BYTES:
        raise ValueError('Eine Datei darf höchstens 5 MB groß sein.')
    truncated = False
    if suffix == '.pdf':
        from pypdf import PdfReader
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError('Verschlüsselte PDFs bitte zuerst entsperren.')
            chunks = []
            for index, page in enumerate(reader.pages):
                if index >= 40 or sum(map(len, chunks)) > MAX_TEXT_CHARS:
                    truncated = True
                    break
                stream = page.get_contents()
                if stream and len(stream.get_data()) > MAX_EXPANDED_BYTES:
                    raise ValueError('Diese PDF-Seite ist zu komplex. Bitte einen Textexport verwenden.')
                chunks.append(f'\n[Seite {index + 1}]\n{page.extract_text() or ""}')
            text = ''.join(chunks)
            if not any(chunk.split(']\n', 1)[-1].strip() for chunk in chunks):
                raise ValueError('Das PDF enthält keinen auslesbaren Text. Für Scans bitte zuerst OCR oder einen Textexport verwenden.')
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError('Das PDF konnte nicht gelesen werden.') from exc
    elif suffix == '.docx':
        try:
            with ZipFile(BytesIO(content)) as archive:
                info = archive.getinfo('word/document.xml')
                if info.file_size > MAX_EXPANDED_BYTES:
                    raise ValueError('Das entpackte Word-Dokument ist zu groß.')
                xml = archive.read(info)
                if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml:
                    raise ValueError('Das Word-Dokument enthält nicht unterstützte XML-Deklarationen.')
                root = ElementTree.fromstring(xml)
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text = '\n'.join(''.join(p.itertext()) for p in root.findall('.//w:p', ns))
        except (BadZipFile, KeyError, ElementTree.ParseError) as exc:
            raise ValueError('Das Word-Dokument konnte nicht gelesen werden.') from exc
    elif suffix in TEXT_EXTENSIONS:
        try:
            text = content.decode('utf-16' if content.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('cp1252', errors='replace')
        if any(ord(char) < 32 and char not in '\n\r\t' for char in text):
            raise ValueError('Die Datei enthält Binärdaten. Bitte einen Textexport verwenden.')
    else:
        raise ValueError('Unterstützt werden PDF mit Text, DOCX und Textdateien (auch DBC, ARXML und LDF).')
    text = text.strip()
    if not text:
        raise ValueError('Die Datei enthält keinen auslesbaren Text.')
    return {'name': name, 'size': len(content), 'format': suffix[1:].upper(),
            'text': text[:MAX_TEXT_CHARS], 'truncated': truncated or len(text) > MAX_TEXT_CHARS}
