## ADDED Requirements

### Requirement: Style matching is maintained
The maintained backend workflows SHALL execute the deterministic style-matching contract suite.

#### Scenario: Style selection regression
- **WHEN** distinct setting inputs collapse to an incorrect default style
- **THEN** both maintained workflows fail before release.
