"""Conservative speech attribution for deterministic perspective checks."""

import re


_ATTRIBUTED_SPEECH = re.compile(
    r"(?:他|她)(?:在[^。！？；;\n，,]{0,12})?(?:对自己)?"
    r"(?:说道|答道|心想|暗想|告诉自己|说|问|想)[，,:：]"
    r"[^。！？；;\n]*"
)


def without_attributed_speech(text: str) -> str:
    """Exclude explicit third-person speech/thought, bounded by the sentence.

    This handles unquoted '他说，我…' without treating an arbitrary occurrence
    of '说' as attribution or hiding first-person narration in the next sentence.
    Ambiguous free indirect speech is outside this deterministic rule's scope.
    """
    return _ATTRIBUTED_SPEECH.sub(" ", text)
