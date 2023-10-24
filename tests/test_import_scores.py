import shutil
from pathlib import Path

from intracursus_import.import_scores import import_scores

TEST_DIR = Path(__file__).parent


def test_intracursus_import(tmp_path):
    ods_file = "Liste-Seance-2-TBFTR106-2023-2024.ods"
    shutil.copy(TEST_DIR / ods_file, tmp_path)
    import_scores(tmp_path / ods_file)
