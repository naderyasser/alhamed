# Contributing to Orfe Cosmetics

Thank you for your interest in contributing to Orfe Cosmetics! This document provides guidelines and instructions for contributing to the project.

## 🤝 How to Contribute

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When creating a bug report, include:

- **Description**: A clear and concise description of the problem
- **Steps to Reproduce**: Steps to reproduce the behavior
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Screenshots**: If applicable, add screenshots to help explain the problem
- **Environment**: 
  - OS: [e.g., Ubuntu 20.04]
  - Python Version: [e.g., 3.8]
  - Browser: [e.g., Chrome 90]

### Suggesting Enhancements

Enhancement suggestions are welcome! Please include:

- **Description**: A clear and concise description of the enhancement
- **Motivation**: Why this enhancement would be useful
- **Alternatives**: Any alternative solutions or features you've considered

### Pull Requests

1. **Fork the repository** and create your branch from `master`
2. **Make your changes** with clear, descriptive commit messages
3. **Test your changes** thoroughly
4. **Update documentation** if needed
5. **Submit a pull request** with a clear description of your changes

## 📋 Development Setup

### Prerequisites

- Python 3.8 or higher
- pip
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/naderyasser/Ecommerce.git
cd Ecommerce
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example environment file:
```bash
cp .env.example .env
```

5. Update the `.env` file with your configuration

6. Run the application:
```bash
python app.py
```

## 🧪 Testing

Before submitting a pull request, ensure:

- [ ] Code follows the existing style
- [ ] All tests pass (if applicable)
- [ ] Documentation is updated
- [ ] No new warnings or errors

## 📝 Code Style

- Follow PEP 8 guidelines for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused and concise

## 📂 Project Structure

```
Orfe-cosmatics/
├── app.py                 # Main application file
├── models/               # Database models
├── templates/            # HTML templates
│   ├── shop/            # Store templates
│   └── admin/           # Admin panel templates
├── static/               # Static files (CSS, JS, images)
├── instance/             # Database files
├── data/                 # Additional data files
└── logs/                 # Application logs
```

## 🔒 Security

- Never commit sensitive information (API keys, passwords, tokens)
- Use environment variables for configuration
- Follow security best practices
- Report security vulnerabilities privately

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 📧 Contact

For questions or discussions:
- Email: orfecosmetics@gmail.com
- Website: orfe-cosmetics.com

---

Thank you for contributing to Orfe Cosmetics! 🎉
