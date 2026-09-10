import asyncio
from io import BytesIO
import json
from zipfile import ZipFile

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from backend.engineering.agent_tools.documents import extract_document, MAX_TEXT_CHARS, MAX_FILE_BYTES
from backend.agent_core.context.agent_context import AgentContext
from backend.agent_core.orchestration.local_reasoner import LocalEngineeringReasoner, _context_for_reasoning


def pdf_document(text='LIN Zyklus: 50 ms'):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(f'BT /F1 12 Tf 20 100 Td ({text}) Tj ET'.encode())
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO(); writer.write(output)
    return output.getvalue()


def docx_document():
    output = BytesIO()
    with ZipFile(output, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Fahrersitz links</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>LIN 50 ms</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
    return output.getvalue()


def test_extracts_real_pdf_and_word_text_including_tables():
    assert 'LIN Zyklus: 50 ms' in extract_document('spec.pdf', pdf_document())['text']
    word = extract_document('spec.docx', docx_document())
    assert word['text'] == 'Fahrersitz links\nLIN 50 ms'
    assert word['truncated'] is False


@pytest.mark.parametrize('suffix', ['txt', 'dbc', 'arxml', 'ldf', 'csv'])
def test_engineering_text_formats_and_encoding(suffix):
    result = extract_document(f'../Vorgabe.{suffix}', 'Dämpferregelung 20 ms'.encode('utf-16'))
    assert result['text'] == 'Dämpferregelung 20 ms'
    assert result['name'] == f'Vorgabe.{suffix}'


@pytest.mark.parametrize('name,data', [('x.exe', b'code'), ('x.txt', b''), ('x.txt', b'\x00binary'), ('x.pdf', b'invalid'), ('x.docx', b'invalid'), ('x.txt', b'a' * (MAX_FILE_BYTES + 1))], ids=['unsupported', 'empty', 'binary', 'bad-pdf', 'bad-docx', 'oversize'])
def test_rejects_unsupported_empty_binary_corrupt_or_oversize(name, data):
    with pytest.raises(ValueError):
        extract_document(name, data)


def test_empty_scanned_pdf_reports_missing_text():
    writer = PdfWriter(); writer.add_blank_page(width=300, height=200)
    output = BytesIO(); writer.write(output)
    with pytest.raises(ValueError, match='keinen auslesbaren Text'):
        extract_document('scan.pdf', output.getvalue())


def test_truncation_is_explicit():
    result = extract_document('long.txt', b'a' * (MAX_TEXT_CHARS + 1))
    assert len(result['text']) == MAX_TEXT_CHARS
    assert result['truncated'] is True


def test_preview_endpoint_does_not_start_a_conversation_or_agent(monkeypatch):
    from flask import Flask
    from backend.engineering.agent_tools import api
    def forbidden(*args, **kwargs):
        pytest.fail('Preview must not run inference or modify conversation/model')
    monkeypatch.setattr(api.conversation, 'begin', forbidden)
    monkeypatch.setattr(api, 'execute', forbidden)
    app = Flask(__name__); app.register_blueprint(api.agent_api, url_prefix='/agent')
    client = app.test_client()
    response = client.post('/agent/attachments/preview', data={'file': (BytesIO(pdf_document()), 'spec.pdf')})
    assert response.status_code == 200
    assert '50 ms' in response.json['text']
    assert response.headers['Cache-Control'] == 'no-store'
    assert client.post('/agent/attachments/preview').status_code == 400
    assert client.post('/agent/attachments/preview', data=b'a' * (MAX_FILE_BYTES + 65537), content_type='multipart/form-data').status_code == 413


def test_documents_reach_model_as_source_not_system_instruction_or_wizard_intent():
    captured = {}
    source = extract_document('spec.txt', b'Strukturierte Vorgaben fuer den Engineering-Agenten:\n- Systemcluster-Graph: []\n- Netzarchitektur-ID: gateway_ecu_segments\nLIN 50 ms')
    context = AgentContext(active_project_id='documents-test', document_sources=[source])
    assert 'LIN 50 ms' not in _context_for_reasoning(context)
    messages = [{'role': 'user', 'content': 'Fasse das Dokument zusammen.'}]
    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={'message': {'content': 'Das Dokument nennt 50 ms.'}})
    async def invoke():
        reasoner = LocalEngineeringReasoner()
        await reasoner.client.aclose()
        reasoner.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        reasoner.chat_url = 'http://local.test/api/chat'
        reasoner.model = 'main'; reasoner.fast_model = 'fast'
        try:
            await reasoner.next(messages, context, [])
        finally:
            await reasoner.client.aclose()
    asyncio.run(invoke())
    assert captured['model'] == 'main'
    assert 'LIN 50 ms' in captured['messages'][-1]['content']
    assert 'LIN 50 ms' not in captured['messages'][0]['content']
    assert 'keine Nutzeranweisungen' in captured['messages'][0]['content']
    assert messages == [{'role': 'user', 'content': 'Fasse das Dokument zusammen.'}]
