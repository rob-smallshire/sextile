"""Breaking text into lines narrow enough for a viewdata frame.

Forty columns is narrow, and posts about retrocomputing are full of URLs, hex
dumps and assembler listings. A word that cannot fit any line is split rather
than dropped or allowed to overrun: losing part of a link address is worse than
an ugly break.
"""


def wrap_text(text: str, width: int) -> list[str]:
    """Break text into lines of at most ``width`` characters.

    Whitespace runs collapse to a single space and no line carries leading or
    trailing space. A word longer than ``width`` is split across as many lines
    as it needs.
    """
    if width < 1:
        raise ValueError(f"width must be at least 1, got {width}")

    lines: list[str] = []
    current = ""
    for word in text.split():
        for piece in _fit(word, width):
            if not current:
                current = piece
            elif len(current) + 1 + len(piece) <= width:
                current = f"{current} {piece}"
            else:
                lines.append(current)
                current = piece
    if current:
        lines.append(current)
    return lines


def _fit(word: str, width: int) -> list[str]:
    """A word, split into pieces that each fit the width."""
    if len(word) <= width:
        return [word]
    return [word[start : start + width] for start in range(0, len(word), width)]
