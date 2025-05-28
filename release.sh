#!/bin/bash
# Combined build and release script for OCDarr Lite

# Get version from command line
VERSION=${1}

# Check if version was provided
if [ -z "$VERSION" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Example: ./release.sh 1.0.0"
    echo ""
    echo "This will:"
    echo "  1. Create git commit and tag"
    echo "  2. Push to GitHub"
    echo "  3. Build multi-arch Docker image"
    echo "  4. Push to Docker Hub"
    exit 1
fi

echo "🚀 Starting OCDarr Lite release process for version: $VERSION"
echo "=================================================="

# Step 1: Git operations
echo ""
echo "📝 Step 1: Git operations"
echo "------------------------"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Write version to VERSION file
echo "Updating VERSION file to $VERSION"
echo "$VERSION" > VERSION

# Update version in webhook_listener.py if it exists
if [ -f "webhook_listener.py" ]; then
    echo "Updating version in webhook_listener.py"
    if ! grep -q "__version__" webhook_listener.py; then
        sed -i '1i__version__ = "'$VERSION'"' webhook_listener.py
    else
        sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" webhook_listener.py
    fi
fi

# Get current branch, prefer 'lite' branch for OCDarr Lite
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "lite" ]; then
    echo "⚠️  Warning: You're on branch '$BRANCH', but OCDarr Lite should be on 'lite' branch"
    echo "   Consider: git checkout lite"
fi
echo "Current branch: $BRANCH"

# Add files
echo "Adding files to git..."
git add .
git add -A

# Check if there are changes to commit
if git diff --staged --quiet; then
    echo "No changes to commit"
else
    # Commit
    echo "Creating commit..."
    git commit -m "OCDarr Lite v$VERSION

- Lightweight episode management system  
- Rule-based automation for TV series
- Smart webhook processing
- Auto-dismissing banner notifications"
fi

# Create tag
echo "Creating tag v$VERSION..."
git tag -a "v$VERSION" -m "OCDarr Lite v$VERSION

Features:
- Streamlined rule management interface
- Webhook processing for Sonarr, Tautulli, Jellyfin, Jellyseerr  
- Smart episode selection based on viewing habits
- Auto-dismiss notification system
- Multi-architecture Docker support"

# Push commits and tags
echo "Pushing to GitHub..."
git push origin $BRANCH
git push origin "v$VERSION"

echo "✅ Git operations completed"

# Step 2: Docker build and push
echo ""
echo "🐳 Step 2: Docker build and push"
echo "--------------------------------"

# Set up buildx
echo "Setting up Docker Buildx..."
docker buildx create --name ocdarr-builder --use || true

# Ensure the builder is running
docker buildx inspect ocdarr-builder --bootstrap

echo "Building OCDarr Lite multi-arch image..."
docker buildx build \
  --platform linux/amd64,linux/arm64,linux/arm/v7 \
  -t vansmak/ocdarr-lite:$VERSION \
  -t vansmak/ocdarr-lite:latest \
  --push \
  .

echo "✅ Docker operations completed"

# Summary
echo ""
echo "🎉 Release Summary"
echo "=================="
echo "Version: $VERSION"
echo "Git tag: v$VERSION"
echo "Git branch: $BRANCH"
echo "Docker images:"
echo "  - vansmak/ocdarr-lite:$VERSION"
echo "  - vansmak/ocdarr-lite:latest"
echo ""
echo "🚀 OCDarr Lite v$VERSION released successfully!"
echo ""
echo "Next steps:"
echo "  - Check GitHub: https://github.com/Vansmak/OCDarr/tree/lite"
echo "  - Check Docker Hub: https://hub.docker.com/r/vansmak/ocdarr-lite"
echo "  - Test with: docker pull vansmak/ocdarr-lite:$VERSION"
