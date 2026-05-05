#!/usr/bin/env python3
"""
Concept Inventory Analyzer - Reusable Edition
══════════════════════════════════════════════════════════════════════════════════
Generates class-level and individualised student PDF reports from:
  • inventory.csv   - question definitions, correct answers, misconceptions
  • responses.csv   - student answer data (e.g. Google Forms export)

Dependencies:
    pip install matplotlib fpdf2 numpy

Usage:
    python concept_inventory_analyzer.py inventory.csv responses.csv

Output:
    • class_report.pdf           - heatmap, section summary, flagged misconceptions
    • student_reports/<Name>.pdf - one per student with strengths & gaps
══════════════════════════════════════════════════════════════════════════════════
"""

import csv
import os
import sys
import tempfile
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
from fpdf import FPDF


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Question:
    number: int
    topic_code: str
    topic_name: str
    correct_answer: str
    misconceptions: Dict[str, str] = field(default_factory=dict)  # {option: description}

@dataclass
class Section:
    code: str
    name: str
    questions: List[int] = field(default_factory=list)  # 1-indexed question numbers

@dataclass
class Student:
    name: str
    answers: List[str] = field(default_factory=list)  # length = num questions
    score: int = 0
    pct: float = 0.0

@dataclass
class QuestionStats:
    number: int
    distribution: Dict[str, int] = field(default_factory=dict)  # {A:count, B:count, ...}
    pct_distribution: Dict[str, float] = field(default_factory=dict)
    pct_correct: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# CSV PARSING - INVENTORY
# ─────────────────────────────────────────────────────────────────────────────

def load_inventory(filepath: str) -> Tuple[List[Question], List[Section]]:
    """
    Reads the inventory CSV file.

    Expected columns:
        question_number, topic_code, topic_name, correct_answer,
        misconception_A, misconception_B, misconception_C, misconception_D

    Returns (questions, sections) where sections are auto-derived from topic_code.
    """
    questions = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        # Normalize header names
        reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames]

        for row in reader:
            q_num = int(row['question_number'].strip())
            correct = row['correct_answer'].strip().upper()

            misconceptions = {}
            for option in ['A', 'B', 'C', 'D']:
                key = f'misconception_{option.lower()}'
                if key in row and row[key].strip():
                    misconceptions[option] = row[key].strip()

            questions.append(Question(
                number=q_num,
                topic_code=row['topic_code'].strip(),
                topic_name=row['topic_name'].strip(),
                correct_answer=correct,
                misconceptions=misconceptions,
            ))

    # Sort by question number
    questions.sort(key=lambda q: q.number)

    # Derive sections by grouping consecutive questions with the same topic_code
    sections = []
    seen_codes = OrderedDict()
    for q in questions:
        if q.topic_code not in seen_codes:
            seen_codes[q.topic_code] = Section(
                code=q.topic_code,
                name=f"{q.topic_code} - {q.topic_name}",
                questions=[q.number],
            )
        else:
            seen_codes[q.topic_code].questions.append(q.number)
    sections = list(seen_codes.values())

    return questions, sections


# ─────────────────────────────────────────────────────────────────────────────
# CSV PARSING - STUDENT RESPONSES
# ─────────────────────────────────────────────────────────────────────────────

def load_responses(filepath: str, num_questions: int) -> List[Student]:
    """
    Reads the student responses CSV (e.g. Google Forms export).

    Auto-detects:
      - Student name column (looks for 'name' in header)
      - Answer columns (next N columns after name, or columns containing 'Q' or 'question')

    Returns list of Student objects.
    """
    students = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader)

        # Find name column
        name_col = None
        for i, h in enumerate(header):
            if 'name' in h.lower() and 'user' not in h.lower():
                name_col = i
                break

        if name_col is None:
            # Fallback: try column index 2 (typical Google Forms: Timestamp, Email, Name)
            name_col = 2 if len(header) > 2 else 0

        # Find answer columns: take the next num_questions columns after name
        # Or, look for columns that start with Q or contain question numbers
        q_start = name_col + 1

        # Verify we have enough columns
        if q_start + num_questions > len(header):
            # Try to find answer columns by looking for columns with A/B/C/D pattern in data
            # For now, just use what we have
            print(f"  Warning: Expected {num_questions} answer columns starting at col {q_start}, "
                  f"but only {len(header) - q_start} columns available.")
            num_questions = min(num_questions, len(header) - q_start)

        for row in reader:
            if len(row) <= name_col:
                continue
            name = row[name_col].strip()
            if not name:
                continue

            answers = []
            for i in range(num_questions):
                col_idx = q_start + i
                if col_idx < len(row):
                    raw = row[col_idx].strip()
                    # Extract letter: handle "A", "A.", "A) text", etc.
                    ans = extract_answer(raw)
                    answers.append(ans)
                else:
                    answers.append('')

            students.append(Student(name=name, answers=answers))

    return students


def extract_answer(raw: str) -> str:
    """Extracts the answer letter from various formats."""
    if not raw:
        return ''
    raw = raw.strip()
    # If single character
    if len(raw) == 1 and raw.upper() in 'ABCD':
        return raw.upper()
    # If starts with a letter followed by punctuation or space
    if len(raw) >= 2 and raw[0].upper() in 'ABCD' and raw[1] in '.):- ':
        return raw[0].upper()
    # If it's just the letter
    first = raw[0].upper()
    if first in 'ABCD':
        return first
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def compute_stats(students: List[Student], questions: List[Question]) -> List[QuestionStats]:
    """Compute per-question statistics."""
    n = len(students)
    stats = []

    for q in questions:
        idx = q.number - 1  # 0-indexed into answers list
        counts = Counter()
        for s in students:
            if idx < len(s.answers) and s.answers[idx]:
                counts[s.answers[idx]] += 1

        pct_dist = {}
        for option in ['A', 'B', 'C', 'D']:
            pct_dist[option] = round(counts.get(option, 0) / n * 100, 1) if n else 0

        pct_correct = pct_dist.get(q.correct_answer, 0)

        stats.append(QuestionStats(
            number=q.number,
            distribution=dict(counts),
            pct_distribution=pct_dist,
            pct_correct=pct_correct,
        ))

    return stats


def score_students(students: List[Student], questions: List[Question]) -> List[Student]:
    """Compute scores for each student."""
    for s in students:
        score = 0
        for q in questions:
            idx = q.number - 1
            if idx < len(s.answers) and s.answers[idx] == q.correct_answer:
                score += 1
        s.score = score
        s.pct = round(score / len(questions) * 100, 1) if questions else 0
    return students


def compute_section_averages(stats: List[QuestionStats], sections: List[Section]) -> List[Tuple[str, float]]:
    """Returns [(section_name, avg_pct_correct), ...]"""
    stats_map = {s.number: s for s in stats}
    results = []
    for sec in sections:
        pcts = [stats_map[q].pct_correct for q in sec.questions if q in stats_map]
        avg = round(sum(pcts) / len(pcts), 1) if pcts else 0
        results.append((sec.name, avg))
    return results


def find_flagged(stats: List[QuestionStats], questions: List[Question],
                 threshold: float = 30.0) -> List[Dict]:
    """Find questions where a distractor exceeds threshold %."""
    q_map = {q.number: q for q in questions}
    flagged = []
    for s in stats:
        q = q_map[s.number]
        for option in ['A', 'B', 'C', 'D']:
            if option != q.correct_answer and s.pct_distribution.get(option, 0) > threshold:
                misconception = q.misconceptions.get(option, 'Unspecified misconception')
                flagged.append({
                    'q': s.number,
                    'topic': f"{q.topic_code} - {q.topic_name}",
                    'distractor': option,
                    'pct': s.pct_distribution[option],
                    'pct_correct': s.pct_correct,
                    'misconception': misconception,
                })
    return flagged


def find_top_missed(stats: List[QuestionStats], questions: List[Question],
                    top_n: int = 10) -> List[Tuple[int, str, float]]:
    """Returns top N most-missed questions: [(q_num, topic, pct_correct), ...]"""
    q_map = {q.number: q for q in questions}
    ranked = sorted(stats, key=lambda s: s.pct_correct)
    results = []
    for s in ranked[:top_n]:
        q = q_map[s.number]
        results.append((s.number, f"{q.topic_code} - {q.topic_name}", s.pct_correct))
    return results


def get_student_misconceptions(student: Student, questions: List[Question]) -> List[Dict]:
    """Get list of misconceptions for a specific student."""
    misconceptions = []
    for q in questions:
        idx = q.number - 1
        if idx < len(student.answers):
            ans = student.answers[idx]
            if ans and ans != q.correct_answer and ans in q.misconceptions:
                misconceptions.append({
                    'q': q.number,
                    'topic': f"{q.topic_code} - {q.topic_name}",
                    'student_answer': ans,
                    'correct_answer': q.correct_answer,
                    'misconception': q.misconceptions[ans],
                })
    return misconceptions


def get_student_section_scores(student: Student, questions: List[Question],
                                sections: List[Section]) -> List[Tuple[str, int, int, float]]:
    """Returns [(section_name, correct, total, pct), ...] for a student."""
    q_map = {q.number: q for q in questions}
    results = []
    for sec in sections:
        correct = 0
        total = len(sec.questions)
        for q_num in sec.questions:
            idx = q_num - 1
            if idx < len(student.answers) and student.answers[idx] == q_map[q_num].correct_answer:
                correct += 1
        pct = round(correct / total * 100, 1) if total else 0
        results.append((sec.name, correct, total, pct))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# CHART GENERATION (matplotlib → temp PNG files)
# ─────────────────────────────────────────────────────────────────────────────

def create_heatmap_image(stats: List[QuestionStats], questions: List[Question],
                          filepath: str):
    """Creates the main heatmap as a PNG image."""
    n_questions = len(questions)
    q_map = {q.number: q for q in questions}

    # Build data matrix: rows = questions, cols = A, B, C, D
    data = np.zeros((n_questions, 4))
    for i, s in enumerate(stats):
        for j, opt in enumerate(['A', 'B', 'C', 'D']):
            data[i, j] = s.pct_distribution.get(opt, 0)

    fig_height = max(8, n_questions * 0.35)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    # Custom colormap for wrong answers (white → orange → red)
    cmap_wrong = mcolors.LinearSegmentedColormap.from_list(
        'wrong', ['#ffffff', '#fff3e0', '#ffcc80', '#ff9800', '#e65100'])

    # Plot each cell
    for i in range(n_questions):
        q = q_map[stats[i].number]
        for j, opt in enumerate(['A', 'B', 'C', 'D']):
            val = data[i, j]
            if opt == q.correct_answer:
                # Green for correct
                intensity = val / 100
                color = (0.2 + 0.6 * (1 - intensity), 0.8, 0.2 + 0.6 * (1 - intensity))
                if val > 0:
                    color = plt.cm.Greens(0.3 + 0.5 * intensity)
                else:
                    color = '#ffffff'
            elif val > 30:
                # Red flag
                color = '#ffcdd2'
            else:
                # Orange scale for wrong
                color = cmap_wrong(val / 50) if val > 0 else '#ffffff'

            rect = plt.Rectangle((j, n_questions - 1 - i), 1, 1,
                                  facecolor=color, edgecolor='#cccccc', linewidth=0.5)
            ax.add_patch(rect)

            # Text
            text_color = '#c62828' if (opt != q.correct_answer and val > 30) else '#333333'
            fontweight = 'bold' if (opt == q.correct_answer or val > 30) else 'normal'
            if val > 0:
                ax.text(j + 0.5, n_questions - 1 - i + 0.5, f'{val:.0f}%',
                       ha='center', va='center', fontsize=7,
                       color=text_color, fontweight=fontweight)

    # Axes
    ax.set_xlim(0, 4)
    ax.set_ylim(0, n_questions)
    ax.set_xticks([0.5, 1.5, 2.5, 3.5])
    ax.set_xticklabels(['A', 'B', 'C', 'D'], fontsize=10, fontweight='bold')
    ax.xaxis.set_ticks_position('top')
    ax.xaxis.set_label_position('top')

    # Y-axis labels: Q# and topic
    y_labels = []
    for i, s in enumerate(stats):
        q = q_map[s.number]
        label = f"Q{s.number} ({q.correct_answer}) {q.topic_code}"
        y_labels.append(label)
    ax.set_yticks([i + 0.5 for i in range(n_questions)])
    ax.set_yticklabels(reversed(y_labels), fontsize=6.5)

    # Right-side: % correct
    ax2 = ax.twinx()
    ax2.set_ylim(0, n_questions)
    ax2.set_yticks([i + 0.5 for i in range(n_questions)])
    pct_labels = []
    for s in reversed(stats):
        pct = s.pct_correct
        pct_labels.append(f'{pct:.0f}%')
    ax2.set_yticklabels(pct_labels, fontsize=7)
    for i, s in enumerate(reversed(stats)):
        color = '#2e7d32' if s.pct_correct >= 75 else '#f57c00' if s.pct_correct >= 50 else '#c62828'
        ax2.get_yticklabels()[i].set_color(color)
        ax2.get_yticklabels()[i].set_fontweight('bold')

    ax.set_title('Response Distribution Heatmap\n(% of class choosing each option)',
                 fontsize=12, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()


def create_section_chart(section_avgs: List[Tuple[str, float]], filepath: str):
    """Creates a horizontal bar chart for section averages."""
    names = [s[0] for s in section_avgs]
    values = [s[1] for s in section_avgs]

    fig, ax = plt.subplots(figsize=(10, max(4, len(names) * 0.5)))

    colors = ['#4caf50' if v >= 75 else '#ff9800' if v >= 50 else '#f44336' for v in values]

    y_pos = range(len(names))
    bars = ax.barh(y_pos, values, color=colors, edgecolor='white', height=0.7)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=8)
    ax.set_xlim(0, 100)
    ax.set_xlabel('% Correct', fontsize=10)
    ax.set_title('Section-Level Performance', fontsize=12, fontweight='bold')

    # Add value labels
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f'{val:.0f}%', va='center', fontsize=8, fontweight='bold')

    # Reference lines
    ax.axvline(x=75, color='#4caf50', linestyle='--', alpha=0.5, linewidth=1)
    ax.axvline(x=50, color='#f44336', linestyle='--', alpha=0.5, linewidth=1)

    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()


def create_student_section_chart(section_scores: List[Tuple[str, int, int, float]],
                                  student_name: str, filepath: str):
    """Creates a bar chart for an individual student's section performance."""
    names = [s[0].split(' - ')[0] for s in section_scores]  # Just the code
    values = [s[3] for s in section_scores]

    fig, ax = plt.subplots(figsize=(8, max(3, len(names) * 0.4)))

    colors = ['#4caf50' if v >= 75 else '#ff9800' if v >= 50 else '#f44336' for v in values]

    y_pos = range(len(names))
    bars = ax.barh(y_pos, values, color=colors, edgecolor='white', height=0.6)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=7)
    ax.set_xlim(0, 100)
    ax.set_xlabel('% Correct', fontsize=9)
    ax.set_title(f'Section Performance - {student_name}', fontsize=10, fontweight='bold')

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f'{val:.0f}%', va='center', fontsize=7)

    ax.axvline(x=75, color='#4caf50', linestyle='--', alpha=0.3, linewidth=1)
    ax.axvline(x=50, color='#f44336', linestyle='--', alpha=0.3, linewidth=1)
    ax.invert_yaxis()
    plt.tight_layout()
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATION - CLASS REPORT
# ─────────────────────────────────────────────────────────────────────────────

class ClassReportPDF(FPDF):
    def __init__(self, title: str = "Concept Inventory Report"):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.title_text = title
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, self.title_text, new_x="LMARGIN", new_y="NEXT", align='L')
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

    def add_title_page(self, title: str, subtitle: str, n_students: int, n_questions: int):
        self.add_page()
        self.ln(60)
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(33, 33, 33)
        self.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(8)
        self.set_font('Helvetica', '', 14)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, subtitle, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(20)
        self.set_font('Helvetica', '', 12)
        self.cell(0, 8, f'{n_students} students  |  {n_questions} questions',
                  new_x="LMARGIN", new_y="NEXT", align='C')

    def add_heatmap_page(self, image_path: str):
        self.add_page(orientation='P')
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Response Distribution Heatmap', new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(2)

        # Calculate image dimensions to fit page
        page_w = self.w - 20  # margins
        page_h = self.h - self.get_y() - 20

        self.image(image_path, x=10, y=self.get_y(), w=page_w, h=page_h, keep_aspect_ratio=True)
        # self.image(image_path, x=10, y=self.get_y(), w=page_w)

    def add_section_summary_page(self, image_path: str):
        self.add_page()
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Section-Level Performance', new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(4)
        self.image(image_path, x=15, w=180)

    def add_flagged_page(self, flagged: List[Dict]):
        self.add_page()
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(33, 33, 33)
        self.cell(0, 10, 'Flagged Misconceptions (>30% chose same wrong answer)',
                  new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(6)

        if not flagged:
            self.set_font('Helvetica', '', 11)
            self.cell(0, 8, 'No questions exceeded the 30% distractor threshold.',
                      new_x="LMARGIN", new_y="NEXT", align='C')
            return

        for f in flagged:
            if self.get_y() > 250:
                self.add_page()

            # Card background
            self.set_fill_color(255, 248, 225)
            self.set_draw_color(245, 124, 0)

            y_start = self.get_y()
            self.set_font('Helvetica', 'B', 10)
            self.set_text_color(33, 33, 33)
            self.cell(0, 7, f"Q{f['q']} - {f['topic']}", new_x="LMARGIN", new_y="NEXT",
                      fill=True)
            self.set_font('Helvetica', '', 9)
            self.set_text_color(80, 80, 80)
            self.cell(0, 6,
                      f"Distractor {f['distractor']}: {f['pct']:.0f}% of class "
                      f"(correct answer: {f['pct_correct']:.0f}%)",
                      new_x="LMARGIN", new_y="NEXT", fill=True)
            self.set_font('Helvetica', 'I', 9)
            self.set_text_color(120, 80, 0)
            self.multi_cell(0, 5, f"Misconception: {f['misconception']}", fill=True)
            self.ln(4)

    def add_top_missed_page(self, top_missed: List[Tuple[int, str, float]]):
        self.add_page()
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(33, 33, 33)
        self.cell(0, 10, f'Top {len(top_missed)} Most-Missed Questions',
                  new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(6)

        # Table header
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(240, 240, 240)
        self.cell(15, 8, 'Rank', border=1, fill=True, align='C')
        self.cell(15, 8, 'Q#', border=1, fill=True, align='C')
        self.cell(120, 8, 'Topic', border=1, fill=True, align='L')
        self.cell(30, 8, '% Correct', border=1, fill=True, align='C')
        self.ln()

        for i, (q_num, topic, pct) in enumerate(top_missed, 1):
            if pct < 30:
                self.set_fill_color(255, 205, 210)
            elif pct < 50:
                self.set_fill_color(255, 224, 178)
            else:
                self.set_fill_color(255, 249, 196)

            self.set_font('Helvetica', 'B', 9)
            self.cell(15, 7, str(i), border=1, fill=True, align='C')
            self.cell(15, 7, str(q_num), border=1, fill=True, align='C')
            self.set_font('Helvetica', '', 8)
            self.cell(120, 7, topic, border=1, fill=True, align='L')
            self.set_font('Helvetica', 'B', 9)
            color = (198, 40, 40) if pct < 30 else (245, 124, 0) if pct < 50 else (33, 33, 33)
            self.set_text_color(*color)
            self.cell(30, 7, f'{pct:.0f}%', border=1, fill=True, align='C')
            self.set_text_color(33, 33, 33)
            self.ln()

    def add_student_scores_page(self, students: List[Student], n_questions: int):
        self.add_page()
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(33, 33, 33)
        self.cell(0, 10, 'Student Scores', new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(4)

        # Class statistics
        scores = [s.score for s in students]
        mean_score = np.mean(scores)
        median_score = np.median(scores)
        std_score = np.std(scores)
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6,
                  f'Mean: {mean_score:.1f}/{n_questions} ({mean_score/n_questions*100:.1f}%)  |  '
                  f'Median: {median_score:.0f}  |  Std Dev: {std_score:.1f}',
                  new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(6)

        # Sort by score descending
        sorted_students = sorted(students, key=lambda s: -s.score)

        # Table header
        self.set_font('Helvetica', 'B', 9)
        self.set_fill_color(240, 240, 240)
        self.cell(10, 7, '#', border=1, fill=True, align='C')
        self.cell(60, 7, 'Student', border=1, fill=True, align='L')
        self.cell(25, 7, 'Score', border=1, fill=True, align='C')
        self.cell(20, 7, '%', border=1, fill=True, align='C')
        self.cell(55, 7, 'Band', border=1, fill=True, align='C')
        self.ln()

        for i, s in enumerate(sorted_students, 1):
            if self.get_y() > 270:
                self.add_page()
                # Re-add header
                self.set_font('Helvetica', 'B', 9)
                self.set_fill_color(240, 240, 240)
                self.cell(10, 7, '#', border=1, fill=True, align='C')
                self.cell(60, 7, 'Student', border=1, fill=True, align='L')
                self.cell(25, 7, 'Score', border=1, fill=True, align='C')
                self.cell(20, 7, '%', border=1, fill=True, align='C')
                self.cell(55, 7, 'Band', border=1, fill=True, align='C')
                self.ln()

            band = get_band(s.pct)
            color = get_band_color(s.pct)

            self.set_font('Helvetica', '', 8)
            self.set_fill_color(255, 255, 255)
            self.cell(10, 6, str(i), border=1, align='C')
            self.cell(60, 6, s.name[:30], border=1, align='L')
            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(*color)
            self.cell(25, 6, f'{s.score}/{n_questions}', border=1, align='C')
            self.cell(20, 6, f'{s.pct:.0f}%', border=1, align='C')
            self.set_text_color(33, 33, 33)
            self.set_font('Helvetica', '', 8)
            self.cell(55, 6, band, border=1, align='C')
            self.ln()


# ─────────────────────────────────────────────────────────────────────────────
# PDF GENERATION - INDIVIDUAL STUDENT REPORT
# ─────────────────────────────────────────────────────────────────────────────

class StudentReportPDF(FPDF):
    def __init__(self, student_name: str, quiz_title: str):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.student_name = student_name
        self.quiz_title = quiz_title
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f'{self.quiz_title} - {self.student_name}',
                  new_x="LMARGIN", new_y="NEXT", align='L')
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')


def generate_student_report(student: Student, questions: List[Question],
                             sections: List[Section], class_mean: float,
                             quiz_title: str, output_dir: str):
    """Generate an individual student PDF report."""
    # Compute student data
    section_scores = get_student_section_scores(student, questions, sections)
    misconceptions = get_student_misconceptions(student, questions)
    n_questions = len(questions)

    # Strengths: sections with >= 75%
    strengths = [(name, pct) for name, _, _, pct in section_scores if pct >= 75]
    # Weaknesses: sections with < 50%
    weaknesses = [(name, pct) for name, _, _, pct in section_scores if pct < 50]

    # Create section chart
    chart_path = tempfile.mktemp(suffix='.png')
    create_student_section_chart(section_scores, student.name, chart_path)

    # Build PDF
    pdf = StudentReportPDF(student.name, quiz_title)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 10, 'Individual Performance Report', new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(4)

    # Student info box
    pdf.set_fill_color(240, 248, 255)
    pdf.set_draw_color(66, 133, 244)
    pdf.rect(15, pdf.get_y(), 180, 30, style='DF')

    y = pdf.get_y() + 4
    pdf.set_xy(20, y)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(80, 7, student.name)
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(80, 7, f'Score: {student.score}/{n_questions} ({student.pct:.0f}%)', align='R')
    pdf.ln(9)
    pdf.set_x(20)
    band = get_band(student.pct)
    band_color = get_band_color(student.pct)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(*band_color)
    pdf.cell(80, 7, f'Band: {band}')
    pdf.set_text_color(100, 100, 100)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(80, 7, f'Class mean: {class_mean:.1f}%', align='R')
    pdf.set_text_color(33, 33, 33)

    pdf.set_y(pdf.get_y() + 18)

    # Section performance chart
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, 'Performance by Section', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.image(chart_path, x=15, w=180)
    pdf.ln(4)

    # Strengths
    if strengths:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(46, 125, 50)
        pdf.cell(0, 8, 'Strengths', new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(33, 33, 33)
        pdf.set_font('Helvetica', '', 9)
        for name, pct in strengths:
            pdf.cell(5, 5, '')
            pdf.cell(0, 5, f'  {name} ({pct:.0f}%)', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Weaknesses
    if weaknesses:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(198, 40, 40)
        pdf.cell(0, 8, 'Priority Areas for Review', new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(33, 33, 33)
        pdf.set_font('Helvetica', '', 9)
        for name, pct in weaknesses:
            pdf.cell(5, 5, '')
            pdf.cell(0, 5, f'  {name} ({pct:.0f}%)', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Misconceptions
    if misconceptions:
        if pdf.get_y() > 220:
            pdf.add_page()

        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_text_color(230, 81, 0)
        pdf.cell(0, 8, 'Identified Misconceptions', new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for m in misconceptions:
            if pdf.get_y() > 260:
                pdf.add_page()

            pdf.set_fill_color(255, 243, 224)
            pdf.set_font('Helvetica', 'B', 8)
            pdf.set_text_color(33, 33, 33)
            pdf.cell(0, 5,
                     f"  Q{m['q']} - {m['topic']}  "
                     f"(You: {m['student_answer']}, Correct: {m['correct_answer']})",
                     new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.set_font('Helvetica', 'I', 8)
            pdf.set_text_color(120, 80, 0)
            pdf.cell(0, 5, f"    {m['misconception']}",
                     new_x="LMARGIN", new_y="NEXT", fill=True)
            pdf.ln(2)

    pdf.set_text_color(33, 33, 33)

    # Recommendations
    if pdf.get_y() > 240:
        pdf.add_page()
    pdf.ln(6)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 8, 'Recommendations', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font('Helvetica', '', 9)

    if student.pct >= 80:
        rec = ("Excellent performance. Focus on the few remaining gaps identified above. "
               "Consider extending into higher-order application and analysis tasks in these topics.")
    elif student.pct >= 60:
        rec = ("Good foundational understanding with some isolated gaps. "
               "Review the misconceptions listed above and work through targeted practice problems "
               "in the priority areas. Pay attention to the specific reasoning errors identified.")
    elif student.pct >= 40:
        rec = ("Mixed performance across topics. Prioritise the weakest sections listed above "
               "and work through the fundamentals before moving to complex problems. "
               "The misconceptions identified suggest some core concepts need re-teaching.")
    else:
        rec = ("Significant gaps across multiple topics. Focus on building foundational understanding "
               "of each topic from first principles. Work through the textbook examples and seek "
               "additional support in the priority areas listed above.")

    pdf.multi_cell(0, 5, rec)

    # Save
    safe_name = "".join(c for c in student.name if c.isalnum() or c in ' -_').strip()
    output_path = os.path.join(output_dir, f'{safe_name}.pdf')
    pdf.output(output_path)

    # Cleanup temp file
    if os.path.exists(chart_path):
        os.remove(chart_path)

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_band(pct: float) -> str:
    if pct >= 90:
        return 'Excellent'
    elif pct >= 75:
        return 'Strong foundation'
    elif pct >= 60:
        return 'Good - isolated gaps'
    elif pct >= 40:
        return 'Mixed - targeted review needed'
    elif pct >= 25:
        return 'Significant gaps'
    else:
        return 'Weak foundations - re-teach needed'


def get_band_color(pct: float) -> Tuple[int, int, int]:
    if pct >= 75:
        return (46, 125, 50)
    elif pct >= 60:
        return (245, 124, 0)
    elif pct >= 40:
        return (230, 81, 0)
    else:
        return (198, 40, 40)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  CONCEPT INVENTORY ANALYZER")
    print("=" * 70)

    # Parse arguments
    if len(sys.argv) < 3:
        print(f"\nUsage: python {sys.argv[0]} <inventory.csv> <responses.csv> [output_dir]")
        print(f"\n  inventory.csv  - Question definitions with correct answers & misconceptions")
        print(f"  responses.csv  - Student response data (e.g. Google Forms export)")
        print(f"  output_dir     - Output directory (default: ./output)")
        sys.exit(1)

    inventory_path = sys.argv[1]
    responses_path = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else './output'

    # Validate inputs
    for path in [inventory_path, responses_path]:
        if not os.path.exists(path):
            print(f"\n  ERROR: File not found: {path}")
            sys.exit(1)

    # Create output directories
    os.makedirs(output_dir, exist_ok=True)
    student_dir = os.path.join(output_dir, 'student_reports')
    os.makedirs(student_dir, exist_ok=True)

    # ─── Load Data ───────────────────────────────────────────────────────────
    print(f"\n  Loading inventory: {inventory_path}")
    questions, sections = load_inventory(inventory_path)
    print(f"  → {len(questions)} questions in {len(sections)} sections")

    print(f"\n  Loading responses: {responses_path}")
    students = load_responses(responses_path, len(questions))
    print(f"  → {len(students)} student responses")

    if not students:
        print("\n  ERROR: No valid student responses found.")
        sys.exit(1)

    # ─── Analysis ────────────────────────────────────────────────────────────
    print(f"\n  Analysing...")
    stats = compute_stats(students, questions)
    students = score_students(students, questions)
    section_avgs = compute_section_averages(stats, sections)
    flagged = find_flagged(stats, questions, threshold=30)
    top_missed = find_top_missed(stats, questions, top_n=10)

    class_mean = np.mean([s.pct for s in students])
    print(f"  → Class mean: {class_mean:.1f}%")
    print(f"  → Flagged misconceptions: {len(flagged)}")

    # ─── Generate Charts ─────────────────────────────────────────────────────
    print(f"\n  Generating charts...")
    heatmap_path = tempfile.mktemp(suffix='_heatmap.png')
    section_chart_path = tempfile.mktemp(suffix='_sections.png')

    create_heatmap_image(stats, questions, heatmap_path)
    create_section_chart(section_avgs, section_chart_path)

    # ─── Generate Class Report PDF ───────────────────────────────────────────
    print(f"  Generating class report PDF...")
    quiz_title = "Concept Inventory Analysis"
    # Try to infer title from inventory filename
    base_name = os.path.splitext(os.path.basename(inventory_path))[0]
    if base_name.lower() != 'inventory':
        quiz_title = base_name.replace('_', ' ').replace('-', ' ').title()

    pdf = ClassReportPDF(title=quiz_title)
    pdf.alias_nb_pages()

    # Title page
    pdf.add_title_page(quiz_title, 'Class Analysis Report',
                       len(students), len(questions))

    # Heatmap
    pdf.add_heatmap_page(heatmap_path)

    # Section summary
    pdf.add_section_summary_page(section_chart_path)

    # Top missed
    pdf.add_top_missed_page(top_missed)

    # Flagged misconceptions
    pdf.add_flagged_page(flagged)

    # Student scores
    pdf.add_student_scores_page(students, len(questions))

    class_report_path = os.path.join(output_dir, 'class_report.pdf')
    pdf.output(class_report_path)
    print(f"  → Saved: {class_report_path}")

    # ─── Generate Individual Student Reports ─────────────────────────────────
    print(f"\n  Generating individual student reports...")
    for i, student in enumerate(students):
        report_path = generate_student_report(
            student, questions, sections, class_mean, quiz_title, student_dir
        )
        print(f"    [{i+1}/{len(students)}] {student.name} → {os.path.basename(report_path)}")

    # ─── Cleanup ─────────────────────────────────────────────────────────────
    for tmp in [heatmap_path, section_chart_path]:
        if os.path.exists(tmp):
            os.remove(tmp)

    # ─── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  COMPLETE")
    print(f"{'=' * 70}")
    print(f"\n  Class report:    {class_report_path}")
    print(f"  Student reports: {student_dir}/ ({len(students)} files)")
    print(f"\n  Class Statistics:")
    print(f"    Mean:   {class_mean:.1f}%")
    print(f"    Median: {np.median([s.pct for s in students]):.1f}%")
    print(f"    Std:    {np.std([s.pct for s in students]):.1f}%")
    print(f"    Range:  {min(s.pct for s in students):.0f}% - {max(s.pct for s in students):.0f}%")
    print()


if __name__ == '__main__':
    main()