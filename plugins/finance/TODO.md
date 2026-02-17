# Finance Plugin -- Planned Components

Bookkeeping, invoicing, expense tracking, and financial reporting for a solo-dev LLC with contract revenue and hosted product subscriptions.

## Agents

### invoice-generator
- **Purpose**: Generate professional invoices from project data, time entries, and contract terms.
- **Model**: sonnet
- **Color**: green (creation)
- **Tools**: Read, Write, Glob, Grep
- **Tags**: function: [finance, operations], scenario: [invoicing], custom: [billing, clients, revenue]
- **Input**: Client info, project name, time-log entries or fixed-price milestones, payment terms
- **Output**: Markdown invoice at `invoices/YYYY-MM-DD-{client}-{number}.md` with line items, subtotal, tax, total, payment instructions
- **Integration**: Reads from operations:time-log CSV, references operations:scope-tracker for milestone billing

### expense-categorizer
- **Purpose**: Categorize and track business expenses for tax preparation.
- **Model**: haiku (quick categorization)
- **Color**: yellow (validation)
- **Tools**: Read, Write
- **Tags**: function: [finance], scenario: [expense-tracking, tax-prep], custom: [expenses, categories, deductions]
- **Input**: Expense description, amount, date, receipt reference
- **Output**: Appends to `expenses/YYYY-expenses.csv` with IRS Schedule C categories (advertising, car/truck, insurance, office, supplies, software subscriptions, etc.)

## Skills

### revenue-tracker
- **Purpose**: Track revenue from contracts, hosted product subscriptions, and support agreements.
- **Tags**: function: [finance, executive], scenario: [revenue-tracking, business-planning], custom: [revenue, mrr, contracts]
- **Mechanism**: Maintains `revenue/YYYY-revenue.csv` with date, source (contract/subscription/support), client, amount, status (invoiced/paid/overdue). Produces monthly summaries.
- **Integration**: Can pull subscription data from Stripe MCP (`mcp__stripe__*` tools)

### tax-prep
- **Purpose**: Aggregate financial data for quarterly estimated tax payments and annual filing.
- **Tags**: function: [finance], scenario: [tax-prep], custom: [taxes, quarterly-estimates, schedule-c]
- **Mechanism**: Reads revenue tracker + expense tracker CSVs. Calculates gross income, deductible expenses, estimated self-employment tax, estimated quarterly payment. Produces summary report.
- **Note**: NOT tax advice. Produces data summaries for CPA review.

## Commands

### expense-log
- **Purpose**: Quick expense entry from the command line.
- **Tags**: function: [finance], scenario: [expense-tracking], custom: [expenses, quick-entry]
- **Mechanism**: `/expense-log $50 GitHub Copilot subscription` -> parses amount, description, auto-categorizes, appends to CSV
- **allowed-tools**: Read, Write

### financial-summary
- **Purpose**: Generate a financial summary for a given period.
- **Tags**: function: [finance, executive], scenario: [financial-reporting], custom: [summary, revenue, expenses, profit]
- **Mechanism**: Reads revenue and expense CSVs for the period. Calculates revenue, expenses, profit/loss, top expense categories, top revenue sources. Produces markdown report.
- **allowed-tools**: Read, Glob, Grep

## Hooks

None planned initially. Consider a monthly reminder hook (SessionStart) that checks if monthly financial close has been done.

## Dependencies on Other Plugins
- **operations**: time-log and scope-tracker feed into invoice-generator
- **stripe**: revenue-tracker can pull live subscription data via Stripe MCP
- **core**: All components use standard tagging convention

## Data Model Notes
- All financial data stored as CSV files (simple, version-controllable, auditable)
- Directory structure: `invoices/`, `expenses/`, `revenue/` at project root or configurable via `.claude/finance.local.md`
- Currency: USD (hardcoded initially, configurable later)
- Tax categories follow IRS Schedule C for US LLC
