# Contributing to Equity Research Application

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Respect all compliance and legal requirements

## Development Setup

1. Fork the repository
2. Clone your fork
3. Create a virtual environment: `python -m venv venv`
4. Install dependencies: `pip install -r requirements.txt`
5. Create a branch: `git checkout -b feature/your-feature-name`

## Guidelines

### Compliance First

**CRITICAL**: All contributions must maintain compliance with:

- SEC EDGAR terms of service
- Website robots.txt files
- API provider terms of service
- Rate limiting requirements
- Data privacy regulations

Never contribute code that:
- Scrapes paywalled content
- Violates robots.txt
- Bypasses rate limits
- Accesses login-protected data without authorization

### Code Standards

1. **Python Style**: Follow PEP 8
2. **Type Hints**: Use type hints where appropriate
3. **Documentation**: Add docstrings to all functions/classes
4. **Logging**: Use the logging module, not print()
5. **Error Handling**: Implement graceful error handling

### Adding New Data Sources

When adding a new data provider:

1. Check their Terms of Service
2. Implement proper rate limiting
3. Add user agent identification
4. Handle API errors gracefully
5. Document API key requirements
6. Provide example configuration

### Testing

Before submitting:

1. Test with multiple tickers
2. Test with missing/invalid data
3. Test rate limiting
4. Test error conditions
5. Verify robots.txt compliance

## Pull Request Process

1. Update README.md if adding features
2. Add/update docstrings
3. Test your changes thoroughly
4. Ensure compliance requirements are met
5. Submit PR with clear description

## Areas for Contribution

We welcome contributions in:

- **New Data Sources**: Additional free/API-based data providers
- **Performance**: Optimization and concurrent downloads
- **Parsing**: Better extraction of segments, management info
- **UI/UX**: Streamlit interface improvements
- **Documentation**: Examples, tutorials, guides
- **Testing**: Unit tests, integration tests
- **Bug Fixes**: Address issues in GitHub

## Questions?

Open an issue for:
- Feature suggestions
- Bug reports
- Clarification questions
- Design discussions

Thank you for contributing! 🙏
