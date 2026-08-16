# Selenium UI Tests

End-to-end UI tests using Selenium WebDriver for the Security Audit Tool frontend.

## Test Files

| File | Description |
|------|-------------|
| `conftest_selenium.py` | Selenium fixtures: driver, backend/frontend processes, helpers |
| `test_selenium_port_scanner.py` | Port Scanner page tests (load, empty state, scan flow, results, radar, whitelist, errors) |
| `test_selenium_navigation_layout.py` | Navigation, layout contract, design tokens, responsive, accessibility |
| `test_selenium_scan_flow.py` | Scan lifecycle, WebSocket real-time, history, whitelist persistence, error recovery, performance |

## Prerequisites

1. **Python dependencies** (already in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```

2. **Frontend dependencies**:
   ```bash
   cd frontend && pnpm install
   ```

3. **Chrome/Firefox** installed on the system

4. **ChromeDriver/GeckoDriver** - Selenium 4 auto-downloads via `selenium-manager`, but you can also install manually:
   ```bash
   # Windows (via winget)
   winget install Google.Chrome
   winget install Selenium.ChromeDriver

   # Or use webdriver-manager (auto)
   pip install webdriver-manager
   ```

## Running Tests

### Run all Selenium tests
```bash
cd backend
pytest tests/test_selenium_*.py -v --selenium
```

### Run specific test file
```bash
pytest tests/test_selenium_port_scanner.py -v --selenium
```

### Run with specific browser
```bash
pytest tests/test_selenium_*.py -v --selenium --selenium-browser=firefox
```

### Run headed (non-headless)
```bash
pytest tests/test_selenium_*.py -v --selenium --selenium-headless=false
```

### Run with custom URLs
```bash
SELENIUM_BASE_URL=http://localhost:5173 \
SELENIUM_API_URL=http://localhost:8000 \
pytest tests/test_selenium_*.py -v --selenium
```

## Test Categories

### Port Scanner Tests (`test_selenium_port_scanner.py`)
- Page load and layout verification
- Empty state handling
- Scan initiation and progress
- Results table functionality
- Whitelist mark/unmark actions
- Radar map visualization
- Error state handling (permission denied)

### Navigation & Layout Tests (`test_selenium_navigation_layout.py`)
- App shell layout (sidebar + topbar)
- Sidebar module navigation
- Module page layout contract compliance
- Design token verification (colors, fonts, spacing)
- Responsive behavior (mobile/desktop)
- Accessibility (focus, text alternatives, ARIA)

### Scan Flow Tests (`test_selenium_scan_flow.py`)
- Complete scan lifecycle
- WebSocket real-time updates
- Scan history navigation
- Whitelist persistence across scans
- Error recovery and retry
- Multi-module navigation state
- Performance benchmarks

## Test Markers

```bash
# Run only selenium tests
pytest -m selenium --selenium

# Run only slow tests
pytest -m slow --selenium

# Exclude slow tests
pytest -m "not slow" --selenium
```

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Selenium Tests
  run: |
    cd backend
    pip install -r requirements.txt
    cd ../frontend && pnpm install && pnpm run build
    cd ../backend
    pytest tests/test_selenium_*.py -v --selenium --selenium-headless=true
  env:
    SELENIUM_BROWSER: chrome
    SELENIUM_HEADLESS: true
```

### Docker Example
```dockerfile
FROM python:3.11-slim

# Install Chrome
RUN apt-get update && apt-get install -y \
    wget gnupg2 \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN cd frontend && pnpm install && pnpm run build

CMD ["pytest", "backend/tests/test_selenium_*.py", "-v", "--selenium", "--selenium-headless=true"]
```

## Troubleshooting

### Tests timeout waiting for elements
- Increase timeouts in conftest or test files
- Check if frontend/backend are accessible at the configured URLs
- Verify the app builds correctly: `cd frontend && pnpm run build`

### WebDriver issues
- Ensure Chrome/Firefox version matches driver version
- Try: `pip install --upgrade selenium webdriver-manager`
- Check Selenium Manager logs: `SELENIUM_LOG_LEVEL=DEBUG pytest ...`

### Port conflicts
- Default ports: Frontend 5173, Backend 8000
- Change via env vars: `SELENIUM_BASE_URL`, `SELENIUM_API_URL`

### Flaky tests
- Add explicit waits instead of `time.sleep()`
- Use `WebDriverWait` with expected conditions
- Check for async rendering delays in React

## Adding New Tests

1. Follow the existing test class structure
2. Use `PageHelpers` from conftest for common actions
3. Add `data-testid` attributes to frontend components for reliable selectors
4. Mark tests with `@pytest.mark.selenium`
5. Use descriptive test names: `test_<feature>_<expected_behavior>`

## Frontend Test IDs

Add these `data-testid` attributes to frontend components for stable selectors:

```tsx
// AppShell
<aside data-testid="sidebar">...</aside>
<header data-testid="topbar">...</header>

// ModulePageLayout
<div data-testid="page-header">
  <h1 data-testid="page-title">{title}</h1>
  <p data-testid="page-description">{description}</p>
</div>
<div data-testid="kpi-row">
  <KpiCard data-testid="kpi-card" data-tone={tone} ... />

// Panel
<div data-testid="panel">
  <h2 data-testid="panel-title">{title}</h2>
  <p data-testid="panel-subtitle">{subtitle}</p>

// PortScannerPage
<button data-testid="scan-button">Quét ngay</button>
<div data-testid="progress-bar" data-testid="progress-text">{message}</div>
<table data-testid="data-table">...</table>
<StatusBadge data-testid="status-badge" data-tone={tone} ... />
<div data-testid="radar-map">...</div>
<div data-testid="radar-dot" ... />
<button data-testid="mark-safe-btn">...</button>
<div data-testid="empty-state">...</div>
<div data-testid="error-banner" data-tone={tone}>...</div>
<button data-testid="retry-btn">Tải lại</button>

// NavItem
<nav data-testid="nav-item-port-scanner" data-module="port-scanner" data-status="active">...</nav>
<nav data-testid="nav-item-firewall-check" data-module="firewall-check" data-status="coming-soon">...</nav>
```