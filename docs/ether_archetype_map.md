# Ether Archetype Map — Sephira → Psychographic Signal Mapping

> This document is the authoritative reference for how observable session signals
> map to the ten Sephira archetypes in the `LearnerEtherProfile`.
> Do not expose Sephira names externally — use the Guardian Report translations below.

---

## Signal Definitions

| Signal Key | Description | Range |
|---|---|---|
| `response_speed_percentile` | Learner's speed rank vs grade cohort | 0–1 |
| `first_attempt_accuracy` | Fraction correct on first try | 0–1 |
| `reattempt_rate` | Fraction of questions re-attempted | 0–1 |
| `time_on_task_percentile` | Time spent rank vs cohort | 0–1 |
| `skip_rate` | Fraction of questions skipped | 0–1 |
| `error_recovery_rate` | Fraction of errors followed by correct retry | 0–1 |
| `challenge_seek_rate` | Fraction of time learner chose harder options | 0–1 |
| `creative_response_rate` | Open-ended / creative response engagement | 0–1 |
| `engagement_variance` | Variance in session engagement across topics | 0–1 |
| `structured_task_accuracy` | Accuracy on procedural / step-by-step tasks | 0–1 |
| `concrete_task_accuracy` | Accuracy on concrete, real-world tasks | 0–1 |
| `story_engagement` | Engagement with narrative-framed questions | 0–1 |
| `abstract_reasoning_score` | Score on abstract / conceptual questions | 0–1 |
| `warmth_level_signal` | Responsiveness to encouragement in prompts | 0–1 |
| `balance_score` | Average across all signal dimensions | 0–1 |
| `social_signal_responses` | Engagement with collaborative / social context | 0–1 |
| `hands_on_preference` | Preference for hands-on / practical tasks | 0–1 |
| `note_taking_signals` | Evidence of systematic note-taking behaviour | 0–1 |
| `encouragement_responses` | Positive response to warm, encouraging tone | 0–1 |

---

## Sephira Classification Table

### Keter — The Crown Synthesiser
- **Signals:** `abstract_reasoning_score ≥ 0.85`, `skip_rate ≤ 0.10`
- **Pedagogical character:** Intuitive big-picture thinker; thrives on conceptual connections
- **Prompt style:** Abstract, systems-level, minimal hand-holding
- **Metaphor style:** Analytical
- **Narrative frame:** Explorer
- **Guardian Report language:** *"Your child demonstrates advanced conceptual reasoning and prefers to understand the 'why' behind topics."*

---

### Chokhmah — The Flash Insight
- **Signals:** `response_speed_percentile ≥ 0.80`, `first_attempt_accuracy ≥ 0.75`
- **Pedagogical character:** Fast pattern recogniser; gets things quickly on first exposure
- **Prompt style:** Concise, stimulating, minimal scaffolding
- **Metaphor style:** Visual
- **Narrative frame:** Explorer
- **Guardian Report language:** *"Your child learns rapidly and responds well to new challenges. Brief, stimulating explanations work best."*

---

### Binah — The Deep Analyst
- **Signals:** `reattempt_rate ≥ 0.40`, `time_on_task_percentile ≥ 0.60`
- **Pedagogical character:** Methodical; needs time to fully internalise before moving on
- **Prompt style:** Thorough, step-by-step, space for reflection
- **Metaphor style:** Analytical
- **Narrative frame:** Builder
- **Guardian Report language:** *"Your child is a deep thinker who benefits from detailed explanations and time to reflect before moving on."*

---

### Chesed — The Relational Learner
- **Signals:** `encouragement_responses ≥ 0.70`, `warmth_level_signal ≥ 0.70`
- **Pedagogical character:** Motivation is driven by warmth and relationship
- **Prompt style:** Warm, encouraging, affirming, collaborative context
- **Metaphor style:** Narrative
- **Narrative frame:** Healer
- **Guardian Report language:** *"Your child flourishes with encouragement and responds strongly to a warm, supportive learning environment."*

---

### Gevurah — The Disciplined Achiever
- **Signals:** `challenge_seek_rate ≥ 0.60`, `error_recovery_rate ≥ 0.70`
- **Pedagogical character:** Driven by structure, rigour, and the satisfaction of mastering hard problems
- **Prompt style:** Direct, rigorous, clear standards, stretch goals
- **Metaphor style:** Analytical
- **Narrative frame:** Hero
- **Guardian Report language:** *"Your child is self-motivated by challenge and persists through difficult problems with determination."*

---

### Tiferet — The Balanced Learner (Default/Neutral)
- **Signals:** `balance_score` in range 0.40–0.70
- **Pedagogical character:** Adapts well to varied content types; no strong dominant pattern
- **Prompt style:** Moderate balance of warmth, structure, and challenge
- **Metaphor style:** Narrative
- **Narrative frame:** Explorer
- **Guardian Report language:** *"Your child is a well-rounded learner who engages consistently across different types of content."*

---

### Netzach — The Creative Responder
- **Signals:** `creative_response_rate ≥ 0.60`, `engagement_variance ≥ 0.50`
- **Pedagogical character:** Emotionally and aesthetically driven; engagement varies by interest
- **Prompt style:** Evocative, aesthetic, emotionally resonant, SA cultural context
- **Metaphor style:** Visual
- **Narrative frame:** Hero
- **Guardian Report language:** *"Your child engages deeply with creative and imaginative content and benefits from colourful, expressive learning experiences."*

---

### Hod — The Methodical Systematiser
- **Signals:** `structured_task_accuracy ≥ 0.75`, `note_taking_signals ≥ 0.50`
- **Pedagogical character:** Prefers clear procedures, step-by-step systems, organised information
- **Prompt style:** Structured, numbered steps, clear organisation
- **Metaphor style:** Analytical
- **Narrative frame:** Builder
- **Guardian Report language:** *"Your child excels with well-structured, systematic approaches and benefits from clearly organised learning materials."*

---

### Yesod — The Narrative Connector
- **Signals:** `social_signal_responses ≥ 0.50`, `story_engagement ≥ 0.60`
- **Pedagogical character:** Learns through story, context, and social meaning
- **Prompt style:** Narrative-rich, character-driven, community context
- **Metaphor style:** Narrative
- **Narrative frame:** Healer
- **Guardian Report language:** *"Your child learns best when content is presented as a story or connected to real people and community contexts."*

---

### Malkuth — The Practical Learner
- **Signals:** `concrete_task_accuracy ≥ 0.60`, `hands_on_preference ≥ 0.70`
- **Pedagogical character:** Needs tangible, concrete, real-world examples; abstract concepts must be grounded
- **Prompt style:** Concrete, real-world SA examples (braai, rands, spaza shop), hands-on
- **Metaphor style:** Kinesthetic
- **Narrative frame:** Builder
- **Guardian Report language:** *"Your child learns best through practical, hands-on examples connected to everyday South African life."*

---

## Profile Decay Schedule

| Grade Band | Inactivity Threshold | Decay Rate |
|---|---|---|
| Grade R–3 | 7 days | 10% per day toward neutral |
| Grade 4–7 | 14 days | 5% per day toward neutral |
| Grade 8–12 | 30 days | 3% per day toward neutral |

After decay, the profile converges to **Tiferet** (the neutral/balanced archetype).

---

## A/B Shadow Mode

5% of lesson requests run with the baseline (unmodified) prompt in parallel. Engagement signals (completion rate, re-attempt rate, time-on-task) are compared between the Ether-modified and baseline cohorts. Results published to Grafana dashboard: *"Ether Profile Uplift"*.
