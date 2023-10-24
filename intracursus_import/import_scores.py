"""
Import scores of students from an Excel file into an Intracursus file.
"""
from collections import Counter
from dataclasses import field, dataclass
from functools import cache
from pathlib import Path

import pyexcel_ods3  # type: ignore
from fire import Fire  # type: ignore

CONVERSION = (
    "éèêë" "àâ" "ôö" "ùûü" "îï" "ç" "ñ" "-_",
    "eeee" "aa" "oo" "uuu" "ii" "c" "n" "  ",
)
TABLE = str.maketrans(*CONVERSION)

SheetData = list[list[str | float | int]]


@dataclass
class IntracursusData:
    ids: list[int]
    names: list[str]
    scores: list[float | str] = field(default_factory=list)


@dataclass
class OtherData:
    ids: list[int] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    scores: list[float | str] = field(default_factory=list)


class NotAnIntracursusFileError(RuntimeError):
    """Error raised when the file does not look like an Intracursus file."""


class NothingToMergeError(RuntimeError):
    """Error raised when the file doesn't contain another sheet to merge."""


class TooManySheetsError(RuntimeError):
    """Error raised when the file contain more than two sheets."""


class DuplicateNamesError(RuntimeError):
    """Error raised when the same student name is found twice."""


class UnknownNameError(RuntimeError):
    """Error raised when no corresponding name was found in intracursus sheet."""


@cache
def norm(name: str) -> set[str]:
    name = name.casefold()
    # Suppression des accents
    name = name.translate(TABLE)
    return set(name.split())


def match(name1: str, name2: str) -> bool:
    """Test whether A = B, where A and B are names converted to sets of words."""
    return norm(name1) == norm(name2)


def contain(name1: str, name2: str) -> bool:
    """Test whether A ⊂ B or B ⊂ A, where A and B are names converted to sets of words."""
    s1 = norm(name1)
    s2 = norm(name2)
    return s1.issubset(s2) or s2.issubset(s1)


def partial_match(name1: str, name2: str) -> bool:
    """At last resort, test whether A ∩ B ≠ ∅.

    Some students may be registered once with their mother name, and once with their father one,
    so this may prove useful.

    Very small words (length <= 2) like "de" are not considered, since they're meaningless and
    may induce false positives.
    (Ex: "Charles de Gaulle" et "Jean de Lattre de Tassigny").
    """
    intersection = norm(name1) & norm(name2)
    count = sum(1 for word in intersection if len(word) >= 3)
    return count >= 1


def seems_an_intracursus_file(sheet: SheetData) -> bool:
    """Return `True` is the file looks like a valid Intracursus file."""
    return (
        isinstance(sheet[0][0], str)
        and sheet[0][0].startswith("Liste de tous les étudiants  inscrits à l'unité d'enseignement")
        and sheet[1][0]
        == (
            "Les notes acquises ne doivent pas être modifiées."
            " Elles correspondent à la moyenne de l'unité obtenue lors d'une session précédente."
        )
        and sheet[2][0]
        == (
            "On inscrira dans la colonne 'note' ABI ou ABS pour absence injustifiée,"
            " ABJ pour absence justifiée, NEU pour note neutralisée"
        )
        and sheet[5][:4] == ["Numéro", "Nom", "Prénom", "Note"]
    )


def find_first_data_row(other_sheet: SheetData) -> int:
    """Find the line number of the first row containing effective data.

    Skip empty rows and the headers row if any.
    """
    for i, row in enumerate(other_sheet):
        if len([val for val in row if str(val).strip()]) > 0:
            # OK, first Non-empty line found !
            break
    else:
        # All rows are empty.
        raise NothingToMergeError()
    if all(isinstance(val, str) for val in other_sheet[i]):
        # The first non-empty row correspond to the headers, so ignore it.
        i += 1
    return i


def get_other_data(other_sheet: SheetData) -> OtherData:
    i: int = find_first_data_row(other_sheet)
    columns: list[list[str | int | float]] = list(zip(*other_sheet[i:]))  # type: ignore
    ids: list[int] = []
    scores: list[float | str] = []
    names_columns: list[list[str]] = []
    for column in columns:
        if all(isinstance(val, int) and val > 1_000_000 for val in column):
            ids = column  # type: ignore
        elif all(isinstance(val, str) for val in column):
            names_columns.append(column)  # type: ignore
        elif any(isinstance(val, (float, int)) for val in column):
            # Scores to be merged must be the last column that contains numbers.
            # Note that scores column may contain strings too, like "ABI" for example.
            scores = column  # type: ignore
    names: list[str] = [" ".join(vals) for vals in zip(*names_columns)]
    return OtherData(ids=ids, names=names, scores=scores)


def get_intracursus_data(sheet: SheetData) -> IntracursusData:
    return IntracursusData(
        *zip(  # type: ignore
            *(
                (id_, f"{first_name} {last_name}", score)
                for (id_, first_name, last_name, score, *_) in sheet[6:]
            )
        )
    )


def translate_names(
    other_names: list[str], intracursus_names: list[str]
) -> tuple[dict[str, str], dict[str, str]]:
    """Return a dict {name in intracursus sheet: name in other sheet}"""
    others = set(other_names)
    intracursus = set(intracursus_names)

    if len(others) != len(other_names):
        name, count = next((name, count) for name, count in Counter(other_names).items() if count > 1)
        raise DuplicateNamesError(f"The same name was found {count} times: {name!r}.")

    found: dict[str, str] = {}
    to_be_verified: dict[str, str] = {}
    # First pass: same name (without order)
    # Second pass: one name is included in the other
    # Third pass: partial match
    for matching_function in (match, contain, partial_match):
        for other in others:
            for intra in intracursus:
                if matching_function(other, intra):
                    assert intra not in found, (
                        f"Key {intra=} appears already in dict {found=},"
                        f" it should have been removed from {intracursus=} ! "
                    )
                    found[intra] = other
                    if matching_function is partial_match:
                        to_be_verified[intra] = other
        others -= set(found.values())
        intracursus -= set(found)

    for name in others:
        raise UnknownNameError(f"Name not found in Intracursus list: {name!r}.")
    return found, to_be_verified


def update_intracursus_data(intracursus_data: IntracursusData, other_data: OtherData) -> dict[str, str]:
    to_be_verified: dict[str, str] = {}
    if other_data.ids:
        scores: dict[int, float | str] = dict(zip(other_data.ids, other_data.scores))
        intracursus_data.scores = [scores[id_] for id_ in intracursus_data.ids]
    else:
        names_translation, to_be_verified = translate_names(other_data.names, intracursus_data.names)
        scores_: dict[str | None, float | str] = dict(zip(other_data.names, other_data.scores))
        scores_[None] = "ABI"
        intracursus_data.scores = [scores_[names_translation.get(name)] for name in intracursus_data.names]
    return to_be_verified


def fill_scores(intracursus_sheet: SheetData, other_sheet: SheetData) -> None:
    intracursus_data = get_intracursus_data(intracursus_sheet)
    other_data: OtherData = get_other_data(other_sheet)
    to_be_verified = update_intracursus_data(intracursus_data, other_data)
    for i, score in enumerate(intracursus_data.scores, start=6):
        if isinstance(score, str) and score.startswith("#"):
            score = "ABI"
        if not (intracursus_sheet[i][0] == "" and score == "ABI"):
            # Update score, unless there is already a score and new score is unknown ("ABI")
            intracursus_sheet[i][3] = score
        first_name, last_name = intracursus_sheet[i][1:3]
        name = f"{first_name} {last_name}"
        if name in to_be_verified:
            intracursus_sheet[i].append(to_be_verified[name] + " ?")


def import_scores(modified_intracursus_file: Path) -> None:
    """Helper to import students scores inside Intracursus.

    Read an ODS file from Intracursus, with a second sheet manually added containing students names and scores.

    Generate from that a new ODS file with students scores ready to be imported in Intracursus.

    :param modified_intracursus_file: An ODS file downloaded from Intracursus and modified to include scores (XLS files are NOT supported).
    :return:
    """
    if not modified_intracursus_file.is_file():
        raise FileNotFoundError(modified_intracursus_file)
    wb = pyexcel_ods3.get_data(str(modified_intracursus_file))
    all_data = list(wb.values())
    if len(all_data) <= 1:
        raise NothingToMergeError()
    elif len(all_data) > 2:
        raise TooManySheetsError()
    elif not seems_an_intracursus_file(all_data[0]):
        raise NotAnIntracursusFileError(
            f"'{modified_intracursus_file}' does not look like a valid intracursus file."
        )

    fill_scores(*all_data)
    first_sheet_title = list(wb.keys())[0]
    pyexcel_ods3.save_data(
        str(modified_intracursus_file.with_stem(modified_intracursus_file.stem + "-merged")),
        {first_sheet_title: wb[first_sheet_title]},
    )


def main():
    Fire(import_scores)


if __name__ == "__main__":
    import_scores(Path(__file__).parent.parent / "tests/Liste-Seance-2-TBFTR106-2023-2024.ods")
