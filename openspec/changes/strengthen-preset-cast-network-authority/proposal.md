# Strengthen Preset Cast Network Authority

## Why

Production QA showed that a story can technically mention one or two preset
people while the actual plot is driven by a newly invented relationship network.
That still breaks the player's authored setup: the mentor, close friend, and peer
network should remain the authoritative cast for modern career stories instead
of being replaced by debtors, investors, or unrelated genre templates.

## What Changes

- Strengthen preset-cast prompt authority with an explicit 80% relationship
  network rule for multi-person relationship or conflict scenes.
- Tighten the quick validator so generated stories are rejected when they name
  several outside characters while using too little of the preset cast network.
- Treat `relationships.key_people` as the authoritative required cast even when
  family members also appear in the broader available-people list.
- Preserve the existing allowance for focused one-on-one scenes that do not
  introduce a replacement named cast.

## Out Of Scope

- No change to character creation or relationship initialization.
- No external AI calls in tests.
- No change to stories that already follow the preset people and era boundary.
