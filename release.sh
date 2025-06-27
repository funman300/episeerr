#!/bin/bash
# Combined build and release script for Episeerr with Beta Support and Buildx Cleanup
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
    echo "  1. Handle any merge conflicts automatically"
    echo "  2. Create git commit and tag"
    echo "  3. Push to GitHub"
    echo "  4. Build multi-arch Docker image with cleanup"
    echo "  5. Push to Docker Hub"
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

# Step 1: Git operations with conflict handling
echo ""
echo "📝 Step 1: Git operations with conflict resolution"
echo "-------------------------------------------------"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Error: Not in a git repository"
    exit 1
fi

# Handle potential conflicts by fetching and merging first
echo "🔄 Fetching latest changes from GitHub..."
git fetch origin

# Get current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
    echo "⚠️  Warning: You're on branch '$BRANCH'"
    echo "   Consider switching to 'main' branch for releases"
fi
echo "Current branch: $BRANCH"

# Try to merge any remote changes
echo "🔀 Checking for remote changes..."
if ! git merge origin/$BRANCH --no-edit; then
    echo "⚠️  Merge conflicts detected!"
    echo "📝 Auto-resolving common conflicts..."
    
    # Auto-resolve README conflicts by preferring local version
    if git status --porcelain | grep -q "README.md"; then
        echo "   - README.md conflict: using local version"
        git checkout --ours README.md
        git add README.md
    fi
    
    # Auto-resolve VERSION conflicts by using the new version
    if git status --porcelain | grep -q "VERSION"; then
        echo "   - VERSION conflict: using new version ($VERSION)"
        echo "$VERSION" > VERSION
        git add VERSION
    fi
    
    # Check if all conflicts are resolved
    if git status --porcelain | grep -q "^UU\|^AA\|^DD"; then
        echo "❌ Some conflicts still need manual resolution:"
        git status --porcelain | grep "^UU\|^AA\|^DD"
        echo "Please resolve manually and run the script again."
        exit 1
    fi
    
    # Complete the merge
    git commit --no-edit -m "Auto-resolved merge conflicts for release $VERSION"
    echo "✅ Conflicts resolved automatically"
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

⚠️  Pre-release - recommended for testing environments only"
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

# Push commits and tags (no more force!)
echo "📤 Pushing to GitHub..."
if ! git push origin $BRANCH; then
    echo "❌ Error: Failed to push commits to $BRANCH. Check your network or permissions."
    exit 1
fi
if ! git push origin "v$VERSION"; then
    echo "❌ Error: Failed to push tag v$VERSION. Check your network or permissions."
    exit 1
fi

echo "✅ Git operations completed"

# Step 2: Docker build and push with cleanup
echo ""
echo "🐳 Step 2: Docker build and push with automatic cleanup"
echo "------------------------------------------------------"

# Create temporary builder with unique name
BUILDER_NAME="episeerr-builder-$$"
echo "🔧 Creating temporary buildx builder: $BUILDER_NAME"

# Cleanup function
cleanup_buildx() {
    echo ""
    echo "🧹 Cleaning up buildx environment..."
    echo "Removing temporary builder: $BUILDER_NAME"
    docker buildx rm $BUILDER_NAME 2>/dev/null || true
    
    # Clean up any orphaned buildx containers (your annoying ones!)
    echo "Cleaning up orphaned buildx containers..."
    docker container prune -f --filter "label=com.docker.compose.project=buildx" 2>/dev/null || true
    
    # Remove any containers with builder/buildkit in the name
    echo "Removing any remaining builder containers..."
    docker ps -aq --filter "name=builder" | xargs -r docker rm -f 2>/dev/null || true
    docker ps -aq --filter "name=buildkit" | xargs -r docker rm -f 2>/dev/null || true
    
    # Clean up buildx cache
    echo "Pruning buildx cache..."
    docker buildx prune -f 2>/dev/null || true
    
    echo "✅ Buildx cleanup completed - no more annoying containers!"
}

# Set trap for cleanup
trap cleanup_buildx EXIT INT TERM

# Create temporary builder
if ! docker buildx create --name $BUILDER_NAME --use; then
    echo "❌ Failed to create buildx builder"
    exit 1
fi

# Ensure the builder is running
echo "Bootstrapping builder..."
if ! docker buildx inspect $BUILDER_NAME --bootstrap; then
    echo "❌ Failed to bootstrap builder"
    exit 1
fi

# Build with different tagging strategy based on release type
if [ "$IS_PRERELEASE" = true ]; then
    echo "Building Episeerr pre-release multi-arch image (no 'latest' tag)..."
    if docker buildx build \
      --builder $BUILDER_NAME \
      --platform linux/amd64,linux/arm64,linux/arm/v7 \
      -t vansmak/episeerr:$VERSION \
      --push \
      .; then
        
        echo "🧪 Pre-release image built and pushed:"
        echo "  - vansmak/episeerr:$VERSION"
        echo "  - NOT tagged as 'latest' (pre-release)"
    else
        echo "❌ Docker build failed!"
        exit 1
    fi
else
    echo "Building Episeerr stable multi-arch image..."
    if docker buildx build \
      --builder $BUILDER_NAME \
      --platform linux/amd64,linux/arm64,linux/arm/v7 \
      -t vansmak/episeerr:$VERSION \
      -t vansmak/episeerr:latest \
      --push \
      .; then
        
        echo "✅ Stable release images built and pushed:"
        echo "  - vansmak/episeerr:$VERSION"
        echo "  - vansmak/episeerr:latest"
    else
        echo "❌ Docker build failed!"
        exit 1
    fi
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
echo "🧹 Buildx cleanup will complete automatically..."
# Cleanup happens via trap