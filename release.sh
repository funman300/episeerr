#!/bin/bash
# Combined build and release script for Episeerr with Beta Support
# Get version from command line
VERSION=${1}

# Check if version was provided
if [ -z "$VERSION" ]; then
    echo "Usage: ./release.sh <version>"
    echo "Examples:"
    echo "  ./release.sh 1.0.0          (stable release)"
    echo "  ./release.sh beta-1.0.0     (beta release)"
    echo "  ./release.sh 1.0.0-beta.1   (beta release)"
    echo "  ./release.sh 1.0.0-rc.1     (release candidate)"
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

echo "🚀 Starting Episeerr release process for version: $VERSION"
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

# Update version in episeerr.py if it exists
if [ -f "episeerr.py" ]; then
    echo "Updating version in episeerr.py"
    if ! grep -q "__version__" episeerr.py; then
        sed -i '1i__version__ = "'$VERSION'"' episeerr.py
    else
        sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" episeerr.py
    fi
fi

# Get current branch, should be 'main' for Episeerr
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
    echo "⚠️  Warning: You're on branch '$BRANCH'"
    echo "   Consider switching to 'main' branch for releases"
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
        git commit -m "Episeerr v$VERSION (Pre-release)

🧪 Beta/Testing Features:
- Granular episode selection across multiple seasons
- Viewing-based episode automation with webhook integration
- Time-based cleanup with grace periods and dormant timers
- Rule-based episode management system
- Integration with Jellyseerr/Overseerr and Sonarr

⚠️  This is a pre-release version - use for testing only"
    else
        echo "Creating stable release commit..."
        git commit -m "Episeerr v$VERSION

✨ New Features:
- Episode selection system with multi-season support
- Viewing-based automation for episode management
- Time-based cleanup with dual timer system
- Rule-based automation for different show types
- Webhook integration for Tautulli, Jellyfin, and Sonarr
- Tag-based workflow with Jellyseerr/Overseerr integration"
    fi
fi

# Create tag with appropriate message
if [ "$IS_PRERELEASE" = true ]; then
    echo "Creating pre-release tag v$VERSION..."
    git tag -a "v$VERSION" -m "Episeerr v$VERSION (Pre-release)

🧪 Beta Features:
- Multi-season episode selection interface
- Viewing-based episode automation with real-time webhook processing
- Time-based cleanup with grace periods and dormant timers
- Flexible rule system for different show management strategies
- Integration with Jellyseerr/Overseerr request workflows

⚠️  Pre-release - recommended for testing environments only

Testing Focus:
- Episode selection workflow validation
- Webhook processing accuracy (Tautulli/Jellyfin)
- Rule automation with timer-based cleanup
- Multi-season selection interface
- Tag-based request processing"
else
    echo "Creating stable release tag v$VERSION..."
    git tag -a "v$VERSION" -m "Episeerr v$VERSION

Features:
- Complete episode management system with three independent solutions
- Granular episode selection with multi-season support
- Viewing-based automation with webhook integration
- Time-based cleanup with configurable grace and dormant periods
- Rule-based episode management for different show types
- Sonarr integration with tag-based workflows
- Webhook support for Tautulli, Jellyfin, Sonarr, and Jellyseerr/Overseerr
- Multi-architecture Docker support"
fi

# Push commits and tags with force
echo "⚠️  Warning: Force pushing to GitHub. This will overwrite remote changes!"
echo "Pushing to GitHub with --force..."
if ! git push origin $BRANCH --force; then
    echo "❌ Error: Failed to force push commits to $BRANCH. Check your network or permissions."
    exit 1
fi
if ! git push origin "v$VERSION" --force; then
    echo "❌ Error: Failed to force push tag v$VERSION. Check your network or permissions."
    exit 1
fi

echo "✅ Git operations completed"

# Step 2: Docker build and push
echo ""
echo "🐳 Step 2: Docker build and push"
echo "--------------------------------"

# Set up buildx
echo "Setting up Docker Buildx..."
docker buildx create --name episeerr-builder --use || true

# Ensure the builder is running
docker buildx inspect episeerr-builder --bootstrap

# Build with different tagging strategy based on release type
if [ "$IS_PRERELEASE" = true ]; then
    echo "Building Episeerr pre-release multi-arch image (no 'latest' tag)..."
    docker buildx build \
      --platform linux/amd64,linux/arm64,linux/arm/v7 \
      -t vansmak/episeerr:$VERSION \
      --push \
      .
    
    echo "🧪 Pre-release image built and pushed:"
    echo "  - vansmak/episeerr:$VERSION"
    echo "  - NOT tagged as 'latest' (pre-release)"
else
    echo "Building Episeerr stable multi-arch image..."
    docker buildx build \
      --platform linux/amd64,linux/arm64,linux/arm/v7 \
      -t vansmak/episeerr:$VERSION \
      -t vansmak/episeerr:latest \
      --push \
      .
    
    echo "✅ Stable release images built and pushed:"
    echo "  - vansmak/episeerr:$VERSION"
    echo "  - vansmak/episeerr:latest"
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
echo "  - vansmak/episeerr:$VERSION"
if [ "$IS_PRERELEASE" = false ]; then
    echo "  - vansmak/episeerr:latest"
fi

echo ""
if [ "$IS_PRERELEASE" = true ]; then
    echo "🧪 Episeerr v$VERSION (Pre-release) released successfully!"
    echo ""
    echo "⚠️  PRE-RELEASE NOTES:"
    echo "  - This version is for testing purposes"
    echo "  - Not recommended for production use"
    echo "  - Please report issues and feedback"
    echo "  - NOT tagged as 'latest' to prevent accidental use"
else
    echo "🚀 Episeerr v$VERSION released successfully!"
fi

echo ""
echo "Next steps:"
echo "  - Check GitHub: https://github.com/vansmak/episeerr"
if [ "$IS_PRERELEASE" = true ]; then
    echo "  - Check Docker Hub: https://hub.docker.com/r/vansmak/episeerr (pre-release tag)"
    echo "  - Test with: docker pull vansmak/episeerr:$VERSION"
    echo "  - 🧪 Report testing feedback on GitHub Issues"
else
    echo "  - Check Docker Hub: https://hub.docker.com/r/vansmak/episeerr"
    echo "  - Test with: docker pull vansmak/episeerr:$VERSION"
    echo "  - Update documentation if needed"
fi

echo ""
echo "🎯 Episeerr Features Released:"
echo "  - Episode selection system (granular control)"
echo "  - Viewing-based automation (webhook-driven)"
echo "  - Time-based cleanup (grace + dormant timers)"
echo "  - Rule-based management (flexible automation)"
echo "  - Multi-platform support (amd64, arm64, arm/v7)"