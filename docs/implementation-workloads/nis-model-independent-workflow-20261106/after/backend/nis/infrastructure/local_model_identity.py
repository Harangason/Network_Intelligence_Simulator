"""Pure local-provider identity checks shared by inference and saved-code review."""
from __future__ import annotations

import math


def local_model_author(model, info):
    """Admit the selected local completion model, never select a replacement."""
    invalid = ValueError(
        'Das konfigurierte Modell muss ein nachweislich lokal installiertes '
        'GGUF-Sprachmodell mit gültiger Identität und Textausgabe sein. '
        'Cloud-Modelle und unbekannte Ausführungswege sind gesperrt.')
    if not isinstance(model, str) or not model.strip() or not isinstance(info, dict):
        raise invalid
    name = model.lower()
    details, model_info = info.get('details'), info.get('model_info')
    if not isinstance(details, dict) or not isinstance(model_info, dict):
        raise invalid
    family = details.get('family')
    count = model_info.get('general.parameter_count')
    if (info.get('remote_host') or info.get('remote_model') or ':cloud' in name
            or not isinstance(family, str) or not family.strip()
            or type(count) not in (int, float) or not math.isfinite(count) or count <= 0):
        raise invalid
    family = family.lower()
    # Preserve historical author labels and reject a falsely branded identity.
    if name.startswith('qwen'):
        if not family.startswith('qwen'):
            raise invalid
        author = 'QWEN'
    elif name.startswith('llama'):
        if family != 'llama':
            raise invalid
        author = 'LLAMA'
    else:
        author = 'LOCAL_LLM'
    if details.get('format') != 'gguf' and not (
            'format' not in details and author != 'LOCAL_LLM'):
        raise invalid
    capabilities = info.get('capabilities')
    if capabilities is None and author != 'LOCAL_LLM':
        # Historical Ollama metadata and saved Qwen/Llama standards predate
        # capability reporting. New generic identities need explicit evidence.
        return author
    if (not isinstance(capabilities, list) or 'completion' not in capabilities
            or any(not isinstance(item, str) for item in capabilities)):
        raise invalid
    return author
