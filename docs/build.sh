#!/bin/bash

# Build script to convert markdown docs to Jinja templates
# Usage: ./build.sh

set -e  # Exit on error

DOCS_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$DOCS_DIR/../app/templates/docs"
META_TEMPLATE="$DOCS_DIR/docs-meta-template.html"

# Ensure output directory exists
mkdir -p "$TEMPLATE_DIR"

# Function to build a doc page
build_doc() {
    local md_file="$1"
    local title="$2"
    local output_name="$3"

    echo "Building $md_file..."

    # Convert markdown to HTML fragment
    pandoc "$DOCS_DIR/$md_file" -o "$DOCS_DIR/${md_file%.md}.html.fragment" \
        --from markdown \
        --to html5 \
        --wrap=none \
        --no-highlight

    # Read the meta template
    local template_content=$(<"$META_TEMPLATE")

    # Read the fragment
    local fragment_content=$(<"$DOCS_DIR/${md_file%.md}.html.fragment")

    # Replace placeholders
    template_content="${template_content//\{\{TITLE\}\}/$title}"
    template_content="${template_content//\{\{CONTENT\}\}/$fragment_content}"

    # Write to output
    echo "$template_content" > "$TEMPLATE_DIR/$output_name"

    # Clean up fragment
    rm "$DOCS_DIR/${md_file%.md}.html.fragment"

    echo "✓ Generated $TEMPLATE_DIR/$output_name"
}

# Build each doc page
build_doc "quick-start.md" "Quick Start" "quick-start.html"
build_doc "faq.md" "FAQ" "faq.html"

echo ""
echo "✓ All docs built successfully!"
echo "  Templates are in: $TEMPLATE_DIR"
