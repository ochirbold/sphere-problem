#!/bin/bash

# Docker image build script for CVP API
# Usage: ./build-docker.sh [tag]

set -e

# Default values
IMAGE_NAME="cvp-sphere-api"
DEFAULT_TAG="latest"
TAG=${1:-$DEFAULT_TAG}
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

echo "Building Docker image: ${FULL_IMAGE_NAME}"

# Build the Docker image
docker build -t ${FULL_IMAGE_NAME} .

echo "Docker image built successfully: ${FULL_IMAGE_NAME}"

# Show image information
echo ""
echo "Image information:"
docker images | grep ${IMAGE_NAME}

echo ""
echo "To run the image locally:"
echo "  docker run -p 8000:8000 -e DB_USER=your_user -e DB_PASSWORD=your_password ${FULL_IMAGE_NAME}"
echo ""
echo "To push to Docker Hub (if configured):"
echo "  docker tag ${FULL_IMAGE_NAME} yourusername/${FULL_IMAGE_NAME}"
echo "  docker push yourusername/${FULL_IMAGE_NAME}"
echo ""
echo "To save image to file:"
echo "  docker save ${FULL_IMAGE_NAME} | gzip > cvp-sphere-api-${TAG}.tar.gz"