# Prompt: Generate a Concept Inventory Quiz in CSV Format

You are an expert curriculum designer creating a **Concept Inventory** — a diagnostic multiple-choice assessment designed to reveal specific student misconceptions in a subject area.

## Task

Generate a Concept Inventory for the following topic area:

**Subject:** [INSERT SUBJECT, e.g. "IB DP Computer Science"]  
**Topic:** [INSERT TOPIC, e.g. "Topic B — Computational Thinking"]  
**Subtopics to cover:** [INSERT LIST, e.g. "B1.1 Algorithmic design, B1.2 Searching, B1.3 Sorting, B2.1 Abstract data structures"]  
**Number of questions:** [INSERT NUMBER, e.g. 30]  
**Target level:** [INSERT LEVEL, e.g. "Year 12/Grade 11, pre-exam diagnostic"]

## Requirements for Each Question

1. **One unambiguously correct answer** — the answer key must be defensible.
2. **Three carefully designed distractors** — each distractor should represent a **specific, named misconception** that students commonly hold. Do NOT use random wrong answers; each distractor must diagnose a particular reasoning error.
3. **Vary the position of the correct answer** — distribute correct answers roughly equally across A, B, C, D.
4. **Cover Bloom's levels 1–3** — primarily knowledge recall and comprehension, with some application. This is a concept inventory, not a problem-solving test.
5. **Group questions by subtopic** — consecutive questions should share the same topic_code so that sections are auto-detected.

## Misconception Design Principles

- Each distractor should target ONE common misconception
- Misconceptions should be based on: confusing similar concepts, overgeneralising rules, reversing cause/effect, misapplying definitions, conflating related terms
- Write the misconception description as a SHORT phrase (5–15 words) that a teacher would recognise
- Leave the misconception field BLANK for the correct answer column

## Output Format

Produce the output as a CSV file with these exact column headers:

```
question_number,topic_code,topic_name,correct_answer,misconception_A,misconception_B,misconception_C,misconception_D
```

**Rules:**
- `question_number`: sequential integer starting at 1
- `topic_code`: hierarchical code like "B1.1" or "B2.3" — used to auto-group into sections
- `topic_name`: human-readable name for the topic (same for all questions with the same topic_code)
- `correct_answer`: single uppercase letter A, B, C, or D
- `misconception_X`: short description of the misconception for distractor X, or BLANK if X is the correct answer
- Use commas within fields only if the entire field is quoted (standard CSV quoting rules)
- No trailing commas or extra whitespace

## Example Rows

```csv
question_number,topic_code,topic_name,correct_answer,misconception_A,misconception_B,misconception_C,misconception_D
1,B1.1,Algorithmic Design,C,Confuses sequence with selection,Confuses iteration with recursion,,Thinks all algorithms must loop
2,B1.1,Algorithmic Design,A,,Reverses pre-condition and post-condition,Confuses invariant with termination,Algorithm means program code
3,B1.2,Searching Algorithms,B,Binary search works on unsorted data,,Linear search is always O(1),Search requires sorting first always
```

## Additional Instructions

- After the CSV, provide a **separate section** listing the actual question stems and options (A/B/C/D text) so the quiz can be administered. Format this as a numbered list.
- Ensure questions are **standalone** — no question depends on another.
- Avoid "All of the above" or "None of the above" options.
- Avoid negative phrasing ("Which is NOT...") unless testing a specific misconception.
- Questions should be answerable in 30–60 seconds each.

## Begin

Generate the Concept Inventory now for the specification above. Output the CSV first, then the question stems.