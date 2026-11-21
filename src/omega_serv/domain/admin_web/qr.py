"""Encodeur de QR code (ISO/IEC 18004) pour l'activation TOTP, lot 3 du tableau de bord web (decision de l'auteur
du 2026-11-16 : QR code ET methode sans scan, aucune bibliotheque QR installee - donc ecrit ici, sans dependance).

Perimetre volontairement etroit : mode octet, correction d'erreur M (15 %), versions 1 a 10 (213 octets au plus,
largement assez pour un lien `otpauth://`), masque choisi selon les 4 penalites de la norme. Suit l'algorithme de
reference publie par Project Nayuki (QR Code generator library, licence MIT), reecrit pour ce seul besoin. Verifie
par les tests en decodant les images produites avec zbarimg."""
from __future__ import annotations

_ECC_CODEWORDS_PER_BLOCK_M = (10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
_ECC_BLOCKS_M = (1, 1, 1, 2, 2, 4, 4, 4, 5, 5)
_FORMAT_BITS_M = 0
MAX_VERSION = 10


def _num_raw_data_modules(version: int) -> int:
    result = (16 * version + 128) * version + 64
    if version >= 2:
        alignments = version // 7 + 2
        result -= (25 * alignments - 10) * alignments - 55
        if version >= 7:
            result -= 36
    return result


def _num_data_codewords(version: int) -> int:
    return (_num_raw_data_modules(version) // 8
            - _ECC_CODEWORDS_PER_BLOCK_M[version - 1] * _ECC_BLOCKS_M[version - 1])


def _gf_multiply(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coefficient in enumerate(divisor):
            result[i] ^= _gf_multiply(coefficient, factor)
    return result


def _data_codewords(payload: bytes) -> tuple[int, list[int]]:
    for version in range(1, MAX_VERSION + 1):
        count_bits = 8 if version <= 9 else 16
        capacity_bits = _num_data_codewords(version) * 8
        if 4 + count_bits + 8 * len(payload) <= capacity_bits:
            break
    else:
        raise ValueError(f"texte trop long pour un QR code de version {MAX_VERSION} ({len(payload)} octets)")
    bits: list[int] = []

    def append(value: int, length: int) -> None:
        bits.extend((value >> i) & 1 for i in reversed(range(length)))

    append(0b0100, 4)
    append(len(payload), count_bits)
    for byte in payload:
        append(byte, 8)
    append(0, min(4, capacity_bits - len(bits)))
    append(0, -len(bits) % 8)
    codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = 0xEC
    while len(codewords) < capacity_bits // 8:
        codewords.append(pad)
        pad ^= 0xEC ^ 0x11
    return version, codewords


def _with_ecc(version: int, data: list[int]) -> list[int]:
    blocks_count = _ECC_BLOCKS_M[version - 1]
    ecc_length = _ECC_CODEWORDS_PER_BLOCK_M[version - 1]
    raw_codewords = _num_raw_data_modules(version) // 8
    short_blocks = blocks_count - raw_codewords % blocks_count
    short_length = raw_codewords // blocks_count
    divisor = _rs_divisor(ecc_length)
    blocks = []
    k = 0
    for i in range(blocks_count):
        chunk = data[k:k + short_length - ecc_length + (0 if i < short_blocks else 1)]
        k += len(chunk)
        ecc = _rs_remainder(chunk, divisor)
        if i < short_blocks:
            chunk = [*chunk, 0]
        blocks.append(chunk + ecc)
    result = []
    for i in range(len(blocks[0])):
        for j, block in enumerate(blocks):
            if i != short_length - ecc_length or j >= short_blocks:
                result.append(block[i])
    return result


class _Matrix:
    def __init__(self, version: int) -> None:
        self.version = version
        self.size = version * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.function = [[False] * self.size for _ in range(self.size)]

    def set(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self.function[y][x] = True

    def alignment_positions(self) -> list[int]:
        if self.version == 1:
            return []
        count = self.version // 7 + 2
        step = (self.version * 8 + count * 3 + 5) // (count * 4 - 4) * 2
        return [6, *reversed([self.size - 7 - i * step for i in range(count - 1)])]

    def draw_function_patterns(self) -> None:
        for i in range(self.size):
            self.set(6, i, i % 2 == 0)
            self.set(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (self.size - 4, 3), (3, self.size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < self.size and 0 <= y < self.size:
                        self.set(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        positions = self.alignment_positions()
        last = len(positions) - 1
        for i, cx in enumerate(positions):
            for j, cy in enumerate(positions):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format(0)
        if self.version >= 7:
            remainder = self.version
            for _ in range(12):
                remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25)
            bits = self.version << 12 | remainder
            for i in range(18):
                bit = (bits >> i) & 1 == 1
                a, b = self.size - 11 + i % 3, i // 3
                self.set(a, b, bit)
                self.set(b, a, bit)

    def draw_format(self, mask: int) -> None:
        data = _FORMAT_BITS_M << 3 | mask
        remainder = data
        for _ in range(10):
            remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
        bits = (data << 10 | remainder) ^ 0x5412

        def bit(i: int) -> bool:
            return (bits >> i) & 1 == 1

        for i in range(6):
            self.set(8, i, bit(i))
        self.set(8, 7, bit(6))
        self.set(8, 8, bit(7))
        self.set(7, 8, bit(8))
        for i in range(9, 15):
            self.set(14 - i, 8, bit(i))
        for i in range(8):
            self.set(self.size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set(8, self.size - 15 + i, bit(i))
        self.set(8, self.size - 8, True)

    def draw_codewords(self, codewords: list[int]) -> None:
        index = 0
        right = self.size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vertical in range(self.size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = self.size - 1 - vertical if upward else vertical
                    if not self.function[y][x] and index < len(codewords) * 8:
                        self.modules[y][x] = (codewords[index >> 3] >> (7 - (index & 7))) & 1 == 1
                        index += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        rules = (
            lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
            lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
            lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
            lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
        )
        rule = rules[mask]
        for y in range(self.size):
            for x in range(self.size):
                if not self.function[y][x] and rule(x, y):
                    self.modules[y][x] = not self.modules[y][x]

    def penalty(self) -> int:
        size, rows = self.size, self.modules
        columns = [[rows[y][x] for y in range(size)] for x in range(size)]
        score = 0
        finder_like = ((True, False, True, True, True, False, True, False, False, False, False),
                       (False, False, False, False, True, False, True, True, True, False, True))
        for line in (*rows, *columns):
            run = 1
            for i in range(1, size + 1):
                if i < size and line[i] == line[i - 1]:
                    run += 1
                    continue
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
            for i in range(size - 10):
                if tuple(line[i:i + 11]) in finder_like:
                    score += 40
        for y in range(size - 1):
            for x in range(size - 1):
                if rows[y][x] == rows[y][x + 1] == rows[y + 1][x] == rows[y + 1][x + 1]:
                    score += 3
        dark = sum(sum(row) for row in rows)
        total = size * size
        score += ((abs(dark * 20 - total * 10) + total - 1) // total - 1) * 10
        return score


def encode(text: str) -> list[list[bool]]:
    """Matrice du QR code (True = module sombre), sans zone de silence."""
    version, data = _data_codewords(text.encode("utf-8"))
    matrix = _Matrix(version)
    matrix.draw_function_patterns()
    matrix.draw_codewords(_with_ecc(version, data))
    best_mask, best_score = 0, None
    for mask in range(8):
        matrix.apply_mask(mask)
        matrix.draw_format(mask)
        score = matrix.penalty()
        if best_score is None or score < best_score:
            best_mask, best_score = mask, score
        matrix.apply_mask(mask)  # annule (le masque est une inversion)
    matrix.apply_mask(best_mask)
    matrix.draw_format(best_mask)
    return matrix.modules


def to_text(modules: list[list[bool]], quiet: int = 2) -> list[str]:
    """Lignes de terminal, deux modules par caractere (demi-blocs). Un caractere plein = module CLAIR : a afficher en
    noir sur blanc (l'appelant fixe les couleurs), pour que le code reste lisible quel que soit le theme."""
    size = len(modules) + 2 * quiet

    def dark(x: int, y: int) -> bool:
        x, y = x - quiet, y - quiet
        return 0 <= x < len(modules) and 0 <= y < len(modules) and modules[y][x]

    lines = []
    for y in range(0, size, 2):
        line = ""
        for x in range(size):
            top, bottom = not dark(x, y), (y + 1 < size and not dark(x, y + 1))
            line += {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}[(top, bottom)]
        lines.append(line)
    return lines
