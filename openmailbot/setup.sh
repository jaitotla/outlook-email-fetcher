#!/bin/bash

# OpenMailBot - Complete Setup Script
# This script sets up the entire OpenMailBot workspace

set -e

echo "🚀 OpenMailBot - Automated Setup Script"
echo "========================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed. Please install it first.${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ $1 found${NC}"
    fi
}

check_command node
check_command npm
check_command python3
check_command git

echo ""

# Setup directories
cd "$(dirname "$0")"
ROOT_DIR=$(pwd)

echo -e "${BLUE}📁 Setting up workspace structure...${NC}"

# 1. Setup Backend
echo -e "${BLUE}🔧 Setting up Backend (Node.js)...${NC}"
cd "$ROOT_DIR/backend"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created backend .env file${NC}"
fi

if [ ! -d "node_modules" ]; then
    npm install
    echo -e "${GREEN}✓ Installed backend dependencies${NC}"
else
    echo -e "${GREEN}✓ Backend dependencies already installed${NC}"
fi

# 2. Setup Agent
echo -e "${BLUE}🤖 Setting up Python Agent...${NC}"
cd "$ROOT_DIR/agent"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created agent .env file${NC}"
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Created Python virtual environment${NC}"
fi

source venv/bin/activate
pip install -r requirements.txt
echo -e "${GREEN}✓ Installed agent dependencies${NC}"
deactivate

# 3. Setup Frontend
echo -e "${BLUE}🎨 Setting up Frontend (Next.js)...${NC}"
cd "$ROOT_DIR/frontend"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created frontend .env file${NC}"
fi

if [ ! -d "node_modules" ]; then
    npm install
    echo -e "${GREEN}✓ Installed frontend dependencies${NC}"
else
    echo -e "${GREEN}✓ Frontend dependencies already installed${NC}"
fi

# 4. Create main .env
echo -e "${BLUE}⚙️  Creating main .env file...${NC}"
cd "$ROOT_DIR"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created main .env file${NC}"
fi

echo ""
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env files with your credentials:"
echo "   - $ROOT_DIR/.env (Docker compose)"
echo "   - $ROOT_DIR/backend/.env (Backend API)"
echo "   - $ROOT_DIR/agent/.env (Python Agent)"
echo "   - $ROOT_DIR/frontend/.env (Frontend)"
echo ""
echo "2. Start services:"
echo "   - With Docker: docker-compose up -d"
echo "   - Without Docker:"
echo "     cd backend && npm start"
echo "     cd agent && source venv/bin/activate && python main.py"
echo "     cd frontend && npm run dev"
echo ""
echo "3. Access the application:"
echo "   - Frontend: http://localhost:3000"
echo "   - Backend: http://localhost:5000"
echo "   - Agent: http://localhost:8000"
echo ""
echo "📚 For detailed setup instructions, see SETUP.md"
echo ""
echo -e "${GREEN}Happy email managing! 🎉${NC}"
