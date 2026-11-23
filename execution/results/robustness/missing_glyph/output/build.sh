#!/bin/sh
# Rebuild exactly as latex-build-doctor did (run from this output directory).
set -e
export SOURCE_DATE_EPOCH=1704067200 max_print_line=10000
cd "$(dirname "$0")/src/."
xelatex -interaction=nonstopmode -file-line-error -recorder -output-comment=xelatex -no-shell-escape main.tex
echo built: $(pwd)/main.pdf
