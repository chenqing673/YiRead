import os
import hashlib
import json
from core.config import get_data_path
from utils.json_io import write_json_atomic
from utils.json_io import read_json

def translation_revision(result):
    # Presentation-only sentence anchors must not change the saved-text revision.
    blocks=[]
    for block in result.get('blocks',[]):
        value={k:v for k,v in block.items() if k!='reading_units'}
        if value.get('segments'):value['segments']=[{k:v for k,v in s.items() if k!='reading_units'} for s in value['segments']]
        blocks.append(value)
    return hashlib.sha256(json.dumps({'engine':result.get('engine'),'target_lang':result.get('target_lang'),'blocks':blocks},sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]


def get_translation_path():
    path = get_data_path(
        "translation"
    )
    os.makedirs(
        path,
        exist_ok=True
    )
    return path


def save_translation(
    paper_id,
    blocks,
    **metadata
):
    data = {
        "paper_id": paper_id,
        "blocks": blocks,
        **metadata
    }
    file_path = os.path.join(
        get_translation_path(),
        paper_id + ".json"
    )
    write_json_atomic(
        file_path,
        data
    )
    return data


def get_translation(
    paper_id
):
    file_path = os.path.join(
        get_translation_path(),
        paper_id + ".json"
    )
    return read_json(
        file_path
    )
