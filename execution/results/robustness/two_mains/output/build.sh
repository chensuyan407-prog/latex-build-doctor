#!/bin/sh
# Rebuild exactly as latex-build-doctor did (run from this output directory).
set -e
export SOURCE_DATE_EPOCH=1704067200 max_print_line=10000
cd "$(dirname "$0")/src/."
pdflatex -interaction=nonstopmode -file-line-error -recorder -no-shell-escape supplement.tex
echo built: $(pwd)/supplement.pdf
