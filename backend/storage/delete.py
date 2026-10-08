import os
import shutil
from core.config import get_data_path
from utils.json_io import read_json

def delete_paper(paper_id):
    result = {
        "paper_id": paper_id,
        "deleted": []
    }
    # 删除文献目录
    library_path = os.path.join(
        get_data_path("library"),
        paper_id
    )
    if os.path.exists(
        library_path
    ):
        shutil.rmtree(
            library_path
        )
        result["deleted"].append(
            "library"
        )
    # 删除翻译文件
    translation_file = os.path.join(
        get_data_path("translation"),
        paper_id + ".json"
    )
    if os.path.exists(
        translation_file
    ):
        os.remove(
            translation_file
        )
        result["deleted"].append(
            "translation"
        )
    # 删除任务文件
    jobs_path = get_data_path(
        "jobs"
    )
    if os.path.exists(
        jobs_path
    ):
        for filename in os.listdir(
            jobs_path
        ):
            if not filename.endswith(
                ".json"
            ):
                continue
            job_file = os.path.join(
                jobs_path,
                filename
            )
            job = read_json(
                job_file
            )
            if job and job.get(
                "paper_id"
            ) == paper_id:
                os.remove(
                    job_file
                )
                result["deleted"].append(
                    "job:" + filename
                )
    return result
