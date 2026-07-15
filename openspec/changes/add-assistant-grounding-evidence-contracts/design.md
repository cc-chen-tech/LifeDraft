## Context

`AssistantGroundingService` accepts a model payload only after checking it
against `AssistantEvidence`, which is built from player state and the
continuity ledger. The maintained backend gate currently checks neither the
evidence-capacity policy nor the validation branches with a deterministic
provider.

## Goals / Non-Goals

**Goals:**
- Cover retained authoritative evidence and optional evidence-record fields.
- Cover deterministic accepted, uncertain, and rejected assistant answers.
- Keep the contract self-contained, local, and eligible for both maintained
  backend workflows.

**Non-Goals:**
- Do not change assistant prompts, model retry behavior, or production code.
- Do not perform network calls or browser automation.

## Decisions

- Use a small local provider object returning predeclared payloads rather than
  mocks. This tests the production interface while keeping the gate
  deterministic and compliant with the no-mock policy.
- Build state with `SimpleNamespace` and ordinary mappings. This exercises the
  same attribute and mapping paths used by runtime state without test-only
  production hooks.
- Test the evidence cap by filling it with settings, then assert that a wealth
  authority is retained. This targets the documented removal policy directly.
- Add the file to both workflow lists at the same ordered position so both
  gates execute an identical maintained suite.

## Risks / Trade-offs

- [Tests mirror validation details] → Assert observable answer and evidence
  contracts, not private call counts or implementation ordering.
- [Verbose settings could make assertions brittle] → Use generated settings
  only to reach the documented cap and assert stable evidence identifiers.
- [Provider shape can drift] → Keep the local provider to the public
  `generate_completion_json` call signature.

## Migration Plan

The change is additive. CI runs the new test automatically after merge; a
revert removes the test and its two workflow entries with no data migration.

## Open Questions

None.
