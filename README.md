# Concept Inventory tool

# Install dependencies
pip install matplotlib fpdf2 numpy

# Run the analyzer
python concept_inventory_analyzer.py inventory_a1.csv sample_responses.csv ./output

# Output structure:
# ./output/
#   ├── class_report.pdf
#   └── student_reports/
#       ├── Alice Chen.pdf
#       ├── Bob Martinez.pdf
#       ├── Carol Johnson.pdf
#       ├── Dave Wilson.pdf
#       └── Emma Thompson.pdf

