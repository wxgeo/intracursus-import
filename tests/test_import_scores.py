import shutil
from pathlib import Path

import pyexcel_ods3

from intracursus_import.import_scores import import_scores

TEST_DIR = Path(__file__).parent


def test_intracursus_import(tmp_path):
    ods_file = "Liste-Seance-2-TBFTR106-2023-2024.ods"
    shutil.copy(TEST_DIR / ods_file, tmp_path)
    import_scores(str(tmp_path / ods_file))

    data = pyexcel_ods3.get_data(str(tmp_path / ods_file.replace(".ods", "-merged.ods")))
    sheet_data = data["TBFTR106-2020-2021"]
    scores = [score for (id_, last_name, first_name, score, *_) in sheet_data[6:]]

    target = []
    with open(TEST_DIR / "scores.txt") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                line = "ABI"
            if line in ("ABI", "ABJ", "NEU"):
                target.append(line)
            elif line:
                target.append(float(line.replace(",", ".")))
    assert scores == target
    assert sheet_data[10][8] == "alkissi sabrina ?"
