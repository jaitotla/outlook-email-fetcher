# Contributing to OpenMailBot

Thank you for your interest in contributing to OpenMailBot! This document provides guidelines and instructions for contributing.

## 🤝 How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/ankitgoel2004/openmailbot/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots (if applicable)
   - Environment details (OS, Node version, etc.)

### Suggesting Features

1. Check [Discussions](https://github.com/ankitgoel2004/openmailbot/discussions) for similar ideas
2. Open a new discussion in the Ideas category
3. Describe the feature and its benefits
4. Provide examples or mockups if possible

### Submitting Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Test thoroughly
5. Commit with clear messages: `git commit -m "Add feature: description"`
6. Push to your fork: `git push origin feature/your-feature-name`
7. Open a Pull Request

## 🔧 Development Setup

### Prerequisites
- Node.js 18+
- Python 3.9+
- MongoDB
- Neo4j
- Git

### Local Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/openmailbot.git
cd openmailbot/openmailbot

# Run setup
./setup.sh

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start development
docker-compose up -d
```

## 📝 Coding Standards

### JavaScript/TypeScript (Backend & Frontend)
- Use ESLint and Prettier
- Follow Airbnb style guide
- Use meaningful variable names
- Add JSDoc comments for functions
- Write unit tests for new features

### Python (Agent)
- Follow PEP 8
- Use type hints
- Use Black for formatting
- Use MyPy for type checking
- Write docstrings for classes and functions

### Git Commits
Use conventional commit format:
```
feat: add new feature
fix: bug fix
docs: documentation changes
style: formatting changes
refactor: code refactoring
test: add or update tests
chore: maintenance tasks
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
npm test
```

### Agent Tests
```bash
cd agent
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## 📚 Documentation

- Update README.md for user-facing changes
- Add API documentation in docs/API.md
- Update inline code comments
- Include examples in PRs

## 🎯 Areas for Contribution

### High Priority
- [ ] Frontend enhancements and UI/UX improvements
- [ ] Additional LLM provider integrations
- [ ] Enhanced analytics and visualizations
- [ ] Mobile responsiveness improvements
- [ ] Performance optimizations

### Medium Priority
- [ ] Additional email providers (Yahoo, ProtonMail)
- [ ] Team collaboration features
- [ ] Advanced search filters
- [ ] Email templates
- [ ] Integration with other tools (Slack, Teams)

### Low Priority
- [ ] Mobile app (React Native/Flutter)
- [ ] Browser extension
- [ ] Outlook add-in
- [ ] Advanced ML features
- [ ] Internationalization (i18n)

## 🐛 Bug Fixes

Bug fixes are always welcome! Please:
1. Reference the issue number in your PR
2. Add tests to prevent regression
3. Keep changes focused and minimal

## ✨ Feature Development

For new features:
1. Discuss in an issue first
2. Get maintainer approval
3. Break large features into smaller PRs
4. Include tests and documentation

## 🔍 Code Review Process

1. Automated checks must pass (linting, tests)
2. At least one maintainer review required
3. Address all review comments
4. Maintainer will merge when approved

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Celebrated in our community!

## 💬 Getting Help

- **Questions**: [GitHub Discussions](https://github.com/ankitgoel2004/openmailbot/discussions)
- **Chat**: Coming soon
- **Email**: support@openmailbot.dev (coming soon)

## 🎉 Thank You!

Every contribution, no matter how small, makes OpenMailBot better. We appreciate your time and effort!

---

**Happy Coding! 🚀**
