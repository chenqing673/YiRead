import datetime
import uuid

def generate_paper_id():
    date = datetime.datetime.now().strftime(
        "%Y%m%d"
    )
    uid = uuid.uuid4().hex[:8]
    return f"{date}_{uid}"
