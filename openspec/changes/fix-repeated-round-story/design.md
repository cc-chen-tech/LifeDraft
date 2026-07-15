# Design: repeated round-story guard

Canonicalize text by normalizing line endings and whitespace, then compare a candidate against
recent committed event prose. Exact canonical matches and high-overlap long prose are considered
material duplicates. The guard is part of round generation, after basic story validation and
before option generation/persistence.

When a duplicate is detected, the retry prompt explicitly requires a distinct concrete event and
does not accept prior option wording. One retry follows the existing quick-regeneration budget.
If it still duplicates, generation fails visibly rather than saving fake progress.
