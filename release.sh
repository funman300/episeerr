#!/bin/bash
# Combined build and release script for OCDarr with Beta Support
# Get version from command line
VERSION=${1}

# Check if version was provided
if [ -z "$VERSION" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Examples:"
    echo "  ./release.sh 2.1.0          (stable release)"
    echo "  ./release.sh beta-2.1.0     (beta release)"
    echo "  ./release.sh 2.1.0-beta.1   (beta release)"
    echo "  ./release.sh 2.1.0-rc.1     (release candidate)"
    echo ""
    echo "This will:"
    echo "  1. Create git commit and tag"
    echo "  2. Push to GitHub"
    echo "  3. Build multi-arch Docker image"
    echo "  4. Push to Docker Hub"
    echo "  Note: Beta/RC versions won't be tagged as 'latest'"
    exit 1
fi

# Detect if this is a pre-release version
IS_PRERELEASE=false
if [[ $VERSION == *"beta"* ]] || [[ $VERSION == *"alpha"* ]] || [[ $VERSION == *"rc"* ]] || [[ $VERSION == *"-"* ]]; then
    IS_PRERELEASE=true
fi

echo "🚀 Starting OCDarr release process for version: $VERSION"
if [ "$IS_PRERELEASE" = true ]; then
    echo "🧪 Pre-release detected - will NOT tag as 'latest'"
else
    echo "✅ Stable release - will tag as 'latest'"
fi
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
if [ "$BRANCH" != "lite" ] && [ "$BRANCH" != "main" ]; then
    echo "⚠️  Warning: You're on branch '$BRANCH'"
    echo "   Consider switching to 'lite' or 'main' branch for releases"
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
    # Create different commit messages for pre-release vs stable
    if [ "$IS_PRERELEASE" = true ]; then
        echo "Creating pre-release commit..."
        git commit -m "OCDarr v$VERSION (Pre-release)

🧪 Beta/Testing Features:
- Time-based cleanup system with dual timers
- Surgical cleanup (grace period) vs Nuclear cleanup (abandonment)
- Enhanced activity tracking with episode details
- Improved webhook/scheduler separation
- Block-based episode preservation logic

⚠️  This is a pre-release version - use for testing only"
    else
        echo "Creating stable release commit..."
        git commit -m "OCDarr v$VERSION

✨ New Features:
- Time-based cleanup system
- Rule-based automation for TV series
- Smart webhook processing
- Enhanced episode management
- Multi-architecture Docker support"
    fi
fi

# Create tag with appropriate message
if [ "$IS_PRERELEASE" = true ]; then
    echo "Creating pre-release tag v$VERSION..."
    git tag -a "v$VERSION" -m "OCDarr v$VERSION (Pre-release)

🧪 Beta Features:
- Time-based cleanup with grace periods and abandonment timers
- Surgical vs Nuclear cleanup strategies  
- Enhanced activity tracking system
- Webhook/scheduler architectural separation
- Block-based episode preservation

⚠️  Pre-release - recommended for testing environments only

Testing Focus:
- Time-based cleanup logic validation
- Activity tracking accuracy
- Rule processing with new timer fields
- Scheduler status and manual controls"
else
    echo "Creating stable release tag v$VERSION..."
    git tag -a "v$VERSION" -m "OCDarr v$VERSION

Features:
- Complete episode management system
- Rule-based automation with time-based cleanup
- Webhook processing for Sonarr, Tautulli, Jellyfin, Jellyseerr  
- Smart episode selection based on viewing habits
- Multi-architecture Docker support
- Comprehensive logging and monitoring"
fi

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

# Build with different tagging strategy based on release type
if [ "$IS_PRERELEASE" = true ]; then
    echo "Building OCDarr pre-release multi-arch image (no 'latest' tag)..."
    docker buildx build \
      --platform linux/amd64,linux/arm64,linux/arm/v7 \
      -t vansmak/ocdarr:$VERSION \
      --push \
      .
    
    echo "🧪 Pre-release image built and pushed:"
    echo "  - vansmak/ocdarr:$VERSION"
    echo "  - NOT tagged as 'latest' (pre-release)"
else
    echo "Building OCDarr stable multi-arch image..."
    docker buildx build \
      --platform linux/amd64,linux/arm64,linux/arm/v7 \
      -t vansmak/ocdarr:$VERSION \
      -t vansmak/ocdarr:latest \
      --push \
      .
    
    echo "✅ Stable release images built and pushed:"
    echo "  - vansmak/ocdarr:$VERSION"
    echo "  - vansmak/ocdarr:latest"
fi

echo "✅ Docker operations completed"

# Summary
echo ""
echo "🎉 Release Summary"
echo "=================="
echo "Version: $VERSION"
if [ "$IS_PRERELEASE" = true ]; then
    echo "Type: 🧪 PRE-RELEASE"
else
    echo "Type: ✅ STABLE RELEASE"
fi
echo "Git tag: v$VERSION"
echo "Git branch: $BRANCH"
echo "Docker images:"
echo "  - vansmak/ocdarr:$VERSION"
if [ "$IS_PRERELEASE" = false ]; then
    echo "  - vansmak/ocdarr:latest"
fi

echo ""
if [ "$IS_PRERELEASE" = true ]; then
    echo "🧪 OCDarr v$VERSION (Pre-release) released successfully!"
    echo ""
    echo "⚠️  PRE-RELEASE NOTES:"
    echo "  - This version is for testing purposes"
    echo "  - Not recommended for production use"
    echo "  - Please report issues and feedback"
    echo "  - NOT tagged as 'latest' to prevent accidental use"
else
    echo "🚀 OCDarr v$VERSION released successfully!"
fi

echo ""
echo "Next steps:"
echo "  - Check GitHub: https://github.com/Vansmak/OCDarr"
if [ "$IS_PRERELEASE" = true ]; then
    echo "  - Check Docker Hub: https://hub.docker.com/r/vansmak/ocdarr (pre-release tag)"
    echo "  - Test with: docker pull vansmak/ocdarr:$VERSION"
    echo "  - 🧪 Report testing feedback on GitHub Issues"
else
    echo "  - Check Docker Hub: https://hub.docker.com/r/vansmak/ocdarr"
    echo "  - Test with: docker pull vansmak/ocdarr:$VERSION"
    echo "  - Update documentation if needed"
fi