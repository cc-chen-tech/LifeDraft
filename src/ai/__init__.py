"""AI event generation package.

Architecture (post-refactoring):
  client.py              - AIClient: unified AI calling abstraction
  system_prompts.py      - Centralized system prompt registry (KV cache)
  story_generator.py     - StoryGenerator: story text generation
  option_generator.py    - OptionGenerator: option generation + validation
  summary_generator.py   - SummaryGenerator: compression + summaries
  story_rewriter.py      - StoryRewriter: rewriting + regeneration
  profile_synthesizer.py - ProfileSynthesizer: character profile synthesis
  generator.py           - EventGenerator: backward-compatible Facade
  consistency_validator.py - Story consistency validation
  story_analyzer.py      - Dynamic fact extraction
  cache.py               - Event caching
  models.py              - Data models
  utils.py               - Utilities
"""
