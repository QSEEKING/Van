#!/bin/bash
# Release script for CoPaw Code

set -e

VERSION=${1:-"0.1.0"}
VERSION_TAG="v${VERSION}"

echo "=== CoPaw Code Release Script ==="
echo "Version: ${VERSION}"
echo "Tag: ${VERSION_TAG}"
echo ""

# Step 1: Run tests
echo "Step 1: Running tests..."
pytest tests/ --cov=. --cov-report=term-missing -v
if [ $? -ne 0 ]; then
    echo "ERROR: Tests failed!"
    exit 1
fi

# Step 2: Run linting
echo "Step 2: Running linting..."
ruff check .
if [ $? -ne 0 ]; then
    echo "ERROR: Linting failed!"
    exit 1
fi

# Step 3: Check coverage threshold
echo "Step 3: Checking coverage..."
COVERAGE=$(pytest tests/ --cov=. --cov-report=term | grep TOTAL | awk '{print $4}' | sed 's/%//')
if [ ${COVERAGE} -lt 85 ]; then
    echo "ERROR: Coverage ${COVERAGE}% is below 85% threshold!"
    exit 1
fi
echo "Coverage: ${COVERAGE}% ✅"

# Step 4: Build package
echo "Step 4: Building package..."
python -m build
if [ $? -ne 0 ]; then
    echo "ERROR: Build failed!"
    exit 1
fi

# Step 5: Update version in files
echo "Step 5: Updating version..."
# Update pyproject.toml
sed -i "s/version = \"[0-9.]*\"/version = \"${VERSION}\"/" pyproject.toml
# Update config
sed -i "s/version: \"[0-9.]*\"/version: \"${VERSION}\"/" config/default.yaml

# Step 6: Commit changes
echo "Step 6: Committing changes..."
git add -A
git commit -m "Release ${VERSION_TAG}"

# Step 7: Create tag
echo "Step 7: Creating tag..."
git tag ${VERSION_TAG}

echo ""
echo "=== Release ${VERSION_TAG} Ready ==="
echo ""
echo "Next steps:"
echo "  1. Push changes: git push origin main"
echo "  2. Push tag: git push origin ${VERSION_TAG}"
echo "  3. Create GitHub release"
echo "  4. Upload to PyPI: twine upload dist/*"
echo ""