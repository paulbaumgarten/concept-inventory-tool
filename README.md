# Concept Inventory Analyser

A web-based tool for educators to analyze student misconceptions using concept inventory assessments. Generate interactive heatmaps and diagnostic analytics to identify knowledge gaps and common misunderstandings.

**Live Tool:** https://paulbaumgarten.github.io/concept-inventory-tool/

## What Are Concept Inventories?

Concept inventories are diagnostic assessments designed to identify and measure student understanding of key concepts in a subject area. Unlike traditional tests that focus on right/wrong answers, concept inventories explicitly target common misconceptions.

Each question typically includes:
- **Multiple choice options** for the correct answer and plausible misconceptions
- **Misconception descriptions** explaining what each incorrect answer reveals about student thinking
- **Topic codes** for organizing and analyzing results by concept area

By analyzing which incorrect answers students choose, educators gain insights into specific gaps in understanding rather than just overall performance.

## What This Tool Does

The **Concept Inventory Analyser** transforms raw concept inventory data into actionable insights:

### Core Features
- **Upload test specifications** (JSON or CSV format) that define your questions, options, and misconceptions
- **Upload student responses** to analyze how students answered each question
- **Interactive heatmaps** showing which misconceptions are most common
- **Diagnostic analytics** revealing patterns in student thinking
- **Topic-level breakdown** of performance organized by concept area
- **PDF export** of results for sharing with colleagues

### File Processing
- All data processing happens **locally in your browser** — no data is transmitted to external servers
- Supports both **JSON** and **CSV** file formats for maximum flexibility
- Sample files available to help you format your data correctly

## How to Use

### Step 1: Prepare Your Test Specification

Create a file defining your concept inventory questions. Use either JSON or CSV format.

**JSON Format Example:**
```json
[
  {
    "question_number": 1,
    "topic_code": "A1.1",
    "topic_name": "CPU Components",
    "question": "What does the Program Counter store?",
    "options": {
      "A": "The result of the most recent calculation",
      "B": "The address of the next instruction to be fetched",
      "C": "The instruction currently being decoded",
      "D": "The number of instructions executed so far"
    },
    "correct_answer": "B",
    "misconceptions": {
      "A": "PC stores computation results — confuses PC with accumulator",
      "C": "PC tracks current decode stage — confuses PC with IR",
      "D": "PC counts total instructions — misunderstands its role"
    }
  }
]
```

**CSV Format:** See the sample CSV file in the tool for column headers and structure.

### Step 2: Prepare Student Responses

Create a file with student answers in one of the following formats:
- Simple format: `question_number,student_id,answer`
- Extended format: Additional columns for demographics or metadata

Example:
```
question_number,student_id,answer
1,S001,A
1,S002,B
2,S001,C
2,S002,C
```

### Step 3: Upload & Analyze

1. Visit [the live tool](https://paulbaumgarten.github.io/concept-inventory-tool/)
2. Upload your test specification file
3. Upload your student responses file
4. View interactive heatmaps showing:
   - Overall performance by topic
   - Most common misconceptions
   - Student-level response patterns
5. Export results as PDF for further analysis

### Step 4: Interpret Results

Use the heatmaps and analytics to:
- Identify which concepts need reteaching
- Spot systematic misconceptions across your class
- Tailor instruction to address specific gaps
- Track improvement over time by running multiple analyses

## Sample Files

The tool includes sample files to help you get started:
- **Sample JSON test specification** — Ready to use example with CPU architecture questions
- **Sample CSV test specification** — Same questions in CSV format
- **Sample student responses** — Example response data

Download these from the tool interface to understand the expected format.

## Technical Details

### Browser Compatibility
- Works in modern web browsers (Chrome, Firefox, Safari, Edge)
- No installation required — runs entirely in your browser
- JavaScript must be enabled

### Data Privacy
All data processing happens locally in your browser. Your test specifications and student responses are never sent to external servers.

### File Format Support
- **Test Specification:** JSON or CSV
- **Student Responses:** CSV or TSV
- **Export:** PDF

## Getting Started

1. **Start here:** [https://paulbaumgarten.github.io/concept-inventory-tool/](https://paulbaumgarten.github.io/concept-inventory-tool/)
2. **Download sample files** from the tool interface
3. **Format your data** using the samples as a template
4. **Upload and analyze** your concept inventory results

## Tips for Best Results

- Ensure your question numbers are sequential and match between test specs and responses
- Use clear, descriptive misconception labels so teachers understand what each wrong answer indicates
- Include topic codes to organize results by concept area
- Test with sample files first to understand the expected format
- Export results as PDF to share findings with colleagues

## Questions or Feedback?

For issues or suggestions, please check the repository at https://github.com/paulbaumgarten/concept-inventory-tool
