import copy
import ctypes
import json
from typing import List

LANG_MAP = {"English": "en", "Spanish": "es"}
from core.paths import DATA_DIR


def _load_wordlist(lang_code: str) -> list[str]:
    path = DATA_DIR / f"wordlist_{lang_code}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Trie ────────────────────────────────────────────────────────────

class TrieNode:
    __slots__ = ("is_end", "children", "count", "index")

    def __init__(self):
        self.is_end: bool = False
        self.children: dict[str, TrieNode] = {}
        self.count: int = 0
        self.index: int = -1


class Trie:
    def __init__(self, words: list[str]) -> None:
        self.root = TrieNode()
        self.words = words
        self._build()

    def insert(self, word: str, word_id: int) -> None:
        node = self.root
        for c in word:
            if c not in node.children:
                node.children[c] = TrieNode()
            node = node.children[c]
            node.count += 1
        node.is_end = True
        node.index = word_id

    def _build(self) -> None:
        for i, w in enumerate(self.words):
            if len(w) > 3:
                self.insert(w, i)

    def rebuild(self, found_words: list[tuple[str, int]]) -> None:
        for w, w_id in found_words:
            if len(w) > 3:
                self.insert(w, w_id)


# ── Solver ──────────────────────────────────────────────────────────

class WordBoxSolver:
    def __init__(self, language: str = "English") -> None:
        self._language = language
        words = _load_wordlist(LANG_MAP[language])
        self.trie = Trie(words)

        self.found_words: dict[tuple[str, int], list[list[int]]] = {}
        self.letter_grid: List[List[str]] = []
        self.cell_window_positions: List[List[tuple[int, int]]] = []

    # ── Language switching ──────────────────────────────────────────

    def set_language(self, language: str) -> None:
        if language == self._language:
            return
        self._language = language
        words = _load_wordlist(LANG_MAP[language])
        self.trie = Trie(words)
        self.found_words = {}

    @property
    def language(self) -> str:
        return self._language

    # ── Grid helpers ────────────────────────────────────────────────

    def set_letter_grid(self, letter_grid: List[List[str]]) -> None:
        self.letter_grid = letter_grid

    def set_cell_positions(self, contour_info_grid: list[list[tuple[int, int, str]]]) -> None:
        self.cell_window_positions = [
            [(pos[0], pos[1]) for pos in row] for row in contour_info_grid
        ]

    def set_screen_front(self, hwnd: int) -> None:
        ctypes.windll.user32.ShowWindow(hwnd, 5)
        ctypes.windll.user32.SetForegroundWindow(hwnd)

    # ── DFS solve ───────────────────────────────────────────────────

    def solve(self) -> None:
        self.found_words = {}
        for row in range(len(self.letter_grid)):
            for col in range(len(self.letter_grid[0])):
                self._dfs(self.letter_grid, self.trie.root, [], row, col)
        self.trie.rebuild(list(self.found_words.keys()))

    def _is_valid(self, row: int, col: int, rows: int, cols: int) -> bool:
        return 0 <= row < rows and 0 <= col < cols

    def _dfs(
        self,
        grid: List[List[str]],
        node: TrieNode,
        path: List[List[int]],
        row: int,
        col: int,
    ) -> None:
        if not self._is_valid(row, col, len(grid), len(grid[0])) or grid[row][col] == ".":
            return

        char = grid[row][col]
        c0 = char[0]

        if not node or c0 not in node.children or node.children[c0].count == 0:
            return

        node = node.children[c0]
        grid[row][col] = "."

        # Handle multi-character cells (e.g. "qu", "th")
        if len(char) > 1:
            c1 = char[1]
            if node and c1 in node.children:
                node = node.children[c1]
            else:
                grid[row][col] = char
                return

        if not node or node.count < 0:
            grid[row][col] = char
            return

        path.append([row, col])

        if node.is_end:
            word_found = self.trie.words[node.index]
            key = (word_found, node.index)
            self.found_words[key] = copy.deepcopy(path)
            node.is_end = False

            # Pruning
            prune = self.trie.root
            for c in word_found:
                prune = prune.children[c]
                prune.count -= 1

        # 8-directional exploration
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            self._dfs(grid, node, path, row + dr, col + dc)

        grid[row][col] = char
        path.pop()
