#!/bin/bash

# OpenMailBot - Build & Verify Script
# Verifies that all components can be built successfully

set -e

echo "🔍 OpenMailBot - Build Verification"
echo "===================================="
echo ""

cd "$(dirname "$0")"
ROOT_DIR=$(pwd)

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Test Backend
echo -e "${BLUE}🔧 Testing Backend Build...${NC}"
cd "$ROOT_DIR/backend"
if npm install --silent; then
    echo -e "${GREEN}✓ Backend dependencies installed${NC}"
else
    echo -e "${RED}✗ Backend installation failed${NC}"
    exit 1
fi

# Test Agent
echo -e "${BLUE}🤖 Testing Agent Build...${NC}"
cd "$ROOT_DIR/agent"
if python3 -m venv test_venv && source test_venv/bin/activate && pip install --quiet -r requirements.txt; then
    echo -e "${GREEN}✓ Agent dependencies installed${NC}"
    deactivate
    rm -rf test_venv
else
    echo -e "${RED}✗ Agent installation failed${NC}"
    exit 1
fi

# Test Frontend
echo -e "${BLUE}🎨 Testing Frontend Build...${NC}"
cd "$ROOT_DIR/frontend"
if npm install --silent; then
    echo -e "${GREEN}✓ Frontend dependencies installed${NC}"
else
    echo -e "${RED}✗ Frontend installation failed${NC}"
    exit 1
fi

# Verify Docker Compose
echo -e "${BLUE}🐳 Verifying Docker Compose...${NC}"
cd "$ROOT_DIR"
if docker-compose config > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker Compose configuration valid${NC}"
else
    echo -e "${RED}✗ Docker Compose configuration invalid${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All builds verified successfully!${NC}"
echo ""
echo "📝 Next steps:"
echo "1. Configure .env files"
echo "2. Start services: docker-compose up -d"
echo "3. Access: http://localhost:3000"
echo ""
