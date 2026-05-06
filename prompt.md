# Concept Inventory CSV Generation Prompt

Use the prompt below with any LLM (Claude, ChatGPT, Gemini, etc.) to generate a concept inventory test in the correct CSV format for the web analyser tool.

Replace the bracketed sections with your actual subject, topic, and requirements.

---

```
You are an expert curriculum designer creating a Concept Inventory — a diagnostic multiple-choice assessment designed to reveal specific student misconceptions.

Generate a Concept Inventory for the following specification:

  Subject:        [e.g. IB DP Computer Science]
  Topic:          [e.g. Topic A1 — Computer Architecture]
  Subtopics:      [e.g. A1.1 CPU, A1.2 Memory, A1.3 Operating Systems]
  Total questions:[e.g. 30]
  Target level:   [e.g. Year 12, pre-exam diagnostic]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — produce a CSV with this exact header row:

question_number,topic_code,topic_name,question,answer_a,answer_b,answer_c,answer_d,correct_answer,misconception_a,misconception_b,misconception_c,misconception_d

Column definitions:
  question_number — sequential integer starting at 1
  topic_code      — hierarchical code e.g. A1.1, B2.3 (same for all questions in the same subtopic)
  topic_name      — human-readable subtopic name (same for all rows with the same topic_code)
  question        — full question stem text (standalone, no references to other questions)
  answer_a        — text of option A (no "A." prefix)
  answer_b        — text of option B (no "B." prefix)
  answer_c        — text of option C (no "C." prefix)
  answer_d        — text of option D (no "D." prefix)
  correct_answer  — exactly one uppercase letter: A, B, C, or D
  misconception_a — SHORT phrase (5-15 words) describing the misconception a student holds if they choose A;
                    leave BLANK if A is the correct answer
  misconception_b — same for B
  misconception_c — same for C
  misconception_d — same for D

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESIGN RULES:
  1. Every distractor (wrong answer) must target ONE specific, named student misconception
  2. Misconceptions should reflect: confusing similar concepts, reversing cause/effect,
     overgeneralising rules, misapplying definitions, or conflating related terms
  3. Questions test CONCEPTUAL UNDERSTANDING — not memorisation, recall, or calculation
  4. Distribute correct answers roughly evenly across A, B, C, D
  5. Group questions so consecutive rows share the same topic_code
  6. No "all of the above", "none of the above", or negative phrasing ("Which is NOT...")
  7. Each question must be answerable in 30-60 seconds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT RULES:
  • Output ONLY the raw CSV — start with the header row, then data rows
  • No markdown code fences, no preamble, no explanation
  • Use standard CSV quoting: wrap fields containing commas in double quotes
  • Leave misconception cells completely empty (no space, no dash) for the correct answer
```

---

## CSV Format Reference

### Test Specification CSV

Headers must appear in this exact order:

```
question_number,topic_code,topic_name,question,answer_a,answer_b,answer_c,answer_d,correct_answer,misconception_a,misconception_b,misconception_c,misconception_d
```

| Column | Description |
|---|---|
| `question_number` | Sequential integer: 1, 2, 3… |
| `topic_code` | Hierarchical code e.g. `A1.1`, `B2.3` — used to auto-group sections |
| `topic_name` | Human-readable section name (same for all questions sharing the same `topic_code`) |
| `question` | Full question stem text |
| `answer_a` – `answer_d` | Answer choice texts (no letter prefix) |
| `correct_answer` | One of: `A`, `B`, `C`, or `D` |
| `misconception_a` – `misconception_d` | Short description of the misconception for each wrong answer; **leave blank** for the correct answer |

### Student Responses CSV (Google Forms export)

| Column | Content |
|---|---|
| Column 1 | Timestamp (ignored) |
| Column 2 | Email address |
| Column 3 | Student name |
| Columns 4+ | Student's answer for each question: `A`, `B`, `C`, or `D` |

Columns 4 onwards must be in the **same order** as questions in the test specification. Column header names are ignored for answer columns.

**Google Forms tip:** Configure each question's answer options as single letters (A, B, C, D) or ensure the letter is the first character of each option text. The tool extracts the first letter automatically.

---

## Running the Python PDF Generator

For bulk PDF reports (class report + individual student reports):

```bash
pip install matplotlib fpdf2 numpy
python analyse_results.py <test_spec.csv> <student_responses.csv> [output_dir]
```

Note: the Python tool uses the older format without `question`, `answer_a`–`answer_d` columns. It will still work with the extended CSV — the extra columns are simply ignored.
