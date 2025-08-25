import logging
from pathlib import Path
from typing import Union

TEST_FILES_ROOT_PATH = Path(__file__).resolve().parent / "resources" / "docs"


def get_file(file_path: Union[str, Path]) -> bytes:
    p = TEST_FILES_ROOT_PATH / Path(file_path)
    logging.info(f"Reading test file from: {p}")
    return p.read_bytes()


def levenshtein(a: str, b: str) -> int:
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        dp[i][0] = i
    for j in range(len(b) + 1):
        dp[0][j] = j

    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i-1] == b[j-1] else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,      # deletion
                dp[i][j-1] + 1,      # insertion
                dp[i-1][j-1] + cost  # substitution
            )
    return dp[-1][-1]
