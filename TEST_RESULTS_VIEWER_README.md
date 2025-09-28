# 🧠 GödelOS Test Results Viewer

A beautiful, self-contained HTML tool for visualizing test results with interactive features, emoji indicators, and responsive design.

## ✨ Features

- **📊 Interactive Dashboard**: Statistics overview with pass/fail rates and duration
- **🔍 Smart Search**: Search through test names, suites, and file paths
- **🎯 Advanced Filtering**: Filter by test status (passed, failed, skipped, error)
- **📱 Responsive Design**: Works perfectly on desktop, tablet, and mobile
- **🎨 Beautiful UI**: Modern glassmorphism design with smooth animations
- **📁 Drag & Drop**: Simply drag your JSON file onto the viewer
- **🗂️ Collapsible Suites**: Organize tests by suite with expandable sections
- **💡 Error Details**: View detailed error messages and stack traces
- **⚡ Real-time Updates**: Instant filtering and search without page refresh

## 🚀 Quick Start

### Method 1: Simple File Opening
```bash
# Generate test results
python generate_test_results.py

# Open the HTML file in any modern browser
open test_results_viewer.html  # macOS
# or
xdg-open test_results_viewer.html  # Linux
# or double-click the file in Windows
```

> **Tip:** Drop the bundled `sample_test_results.json` onto the viewer (or just open the HTML file without uploading—it's picked up automatically) to explore the UI instantly.

### Method 2: Local Web Server (Recommended)
```bash
# Start the built-in web server
python serve_test_viewer.py

# Your browser will open automatically to:
# http://localhost:8080/test_results_viewer.html
```

### Method 3: Manual pytest JSON Generation
```bash
# Install the pytest JSON reporter
pip install pytest-json-report

# Run tests with JSON output
pytest tests/ --json-report --json-report-file=my_test_results.json

# Upload the generated JSON file to the viewer
```

## 📋 Supported JSON Formats

The viewer automatically detects and handles multiple test result formats:

### 1. pytest-json-report Format (Recommended)
```json
{
  "tests": [
    {
      "nodeid": "tests/unit/test_example.py::test_function",
      "outcome": "passed",
      "duration": 0.123,
      "call": {
        "duration": 0.1,
        "longrepr": "error message if failed"
      }
    }
  ],
  "summary": {
    "total": 10,
    "passed": 8,
    "failed": 2
  }
}
```

### 2. Simple Test Array Format
```json
[
  {
    "name": "test_example",
    "status": "passed",
    "duration": 0.123,
    "message": "",
    "file": "test_file.py",
    "suite": "Example Suite"
  }
]
```

### 3. Custom Results Format
```json
{
  "results": [...],
  "summary": {...}
}
```

### 4. Dynamic Discovery Runner Format
```json
{
  "metadata": { "runner_version": "3.0.0-dynamic-discovery", ... },
  "discovered_categories": { ... },
  "execution_results": {
    "spec_aligned": {
      "tests/spec_aligned/example.py": {
        "passed": true,
        "duration": "0.5s",
        "stderr": "",
        "test_info": {
          "name": "test_example_spec.py",
          "relative_path": "spec_aligned/example/test_example_spec.py"
        }
      }
    }
  }
}
```
The viewer automatically flattens category maps, infers status from boolean `passed` flags, parses duration strings (e.g., `"0.5s"`), and surfaces diagnostics from `stderr`/`error` fields.

## 🎨 UI Components

### Status Indicators
- ✅ **Passed**: Green circle with checkmark
- ❌ **Failed**: Red circle with X mark  
- ⚠️ **Skipped**: Yellow circle with warning
- 💥 **Error**: Orange circle with explosion

### Interactive Elements
- **Search Box**: 🔍 Real-time test filtering
- **Status Filters**: Quick filter buttons for each test state
- **Collapsible Suites**: Click to expand/collapse test groups
- **Progress Bar**: Visual representation of overall pass rate
- **Drag & Drop Zone**: Intuitive file upload area

## 🛠️ Technical Details

### Dependencies
- **Zero external dependencies** - completely self-contained
- Works in any modern browser (Chrome, Firefox, Safari, Edge)
- Uses modern CSS Grid and Flexbox for responsive layout
- Vanilla JavaScript with ES6+ features

### File Structure
```
├── test_results_viewer.html      # Main viewer (self-contained)
├── generate_test_results.py      # Test results generator  
├── serve_test_viewer.py          # Local web server
├── sample_test_results.json      # Example data
└── godelos_test_results.json     # Generated results
```

### Browser Compatibility
- ✅ Chrome 70+
- ✅ Firefox 65+  
- ✅ Safari 12+
- ✅ Edge 79+

## 📈 Example Usage with GödelOS

```bash
# Activate virtual environment
source godelos_venv/bin/activate

# Generate comprehensive test results
python generate_test_results.py

# Start viewer server
python serve_test_viewer.py

# Or run specific tests with JSON output
pytest tests/unit/test_symbol_grounding.py \
  --json-report \
  --json-report-file=symbol_grounding_results.json
```

## 🎯 Test Result Categories

The viewer automatically categorizes and color-codes tests:

| Status | Color | Description |
|--------|-------|-------------|
| **Passed** | 🟢 Green | Test executed successfully |
| **Failed** | 🔴 Red | Test failed with assertion error |
| **Skipped** | 🟡 Yellow | Test was skipped (conditions not met) |
| **Error** | 🟠 Orange | Test had runtime error |

## 🔧 Customization

### Modify Styling
Edit the `<style>` section in `test_results_viewer.html`:
- Change color scheme by updating CSS custom properties
- Modify layout by adjusting Grid/Flexbox properties
- Add animations by extending CSS transitions

### Add Features
Extend the JavaScript `TestResultsViewer` class:
```javascript
// Add custom filters
addCustomFilter(filterName, filterFunction) {
  // Implementation here
}

// Export results
exportResults(format) {
  // PDF, CSV, etc.
}
```

## 🐛 Troubleshooting

### Common Issues
1. **File not loading**: Ensure you're using a web server (not file://) for best compatibility
2. **JSON parse error**: Validate your JSON format using a JSON validator
3. **Empty results**: Check that your JSON contains a `tests` or `results` array
4. **Search not working**: Clear browser cache and reload

### Debug Mode
Open browser developer tools (F12) to see detailed error messages.

## 🤝 Contributing

The test results viewer is designed to be easily extensible:

1. **Add new JSON format support**: Update the `normalizeData()` method
2. **Enhance UI components**: Modify CSS and HTML structure  
3. **Add export features**: Extend JavaScript functionality
4. **Improve responsive design**: Update media queries

## 📄 License

Part of the GödelOS project. See main repository for license details.

---

**💡 Pro Tip**: Use the viewer during development to quickly identify test patterns and focus debugging efforts on the most critical failures!