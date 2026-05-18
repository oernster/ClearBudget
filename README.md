# ClearBudget

A personal budget planning application for managing income, bills, and credit cards with detailed solvency analysis.

## Features

- Month-by-month budget tracking with income and bill templates
- Solvency analysis and forward projections (next 2 months)
- Credit card management: limits, interest rates, payment due dates, utilisation tracking
- Dynamic payment methods: assign bills to bank account or specific credit cards
- Payment due dates auto-adjust to preceding working day (weekends/UK holidays)
- Dark theme UI with tabular data display
- SQLite database for persistent storage

## Application Tabs

- **Month Budget** - View and manage bills for the selected month, assign payment methods
- **Solvency** - Financial health analysis, deficit warnings, forward shortfall projections
- **Credit Cards** - Add, edit, delete cards; track utilisation (OK/WARNING/DANGER status)
- **Archive** - Browse historical month data

## Bill Categories

- housing (Rent, mortgage)
- utilities (Electric, water, internet)
- subscriptions (Recurring services)
- credit_payment (Credit card payments)
- groceries (Food and household)
- discretionary (Entertainment and leisure)
- one_time (One-off purchases)

## Payment Methods

Each bill is assigned to either:
- Bank Account (default) - deducted from bank balance
- Credit Card - tracked separately, affects card utilisation

## Credit Card Tracking

For each card, track:
- Credit limit and current balance
- Interest rate (APR)
- Payment due day (auto-adjusted to working day)
- Card expiry date
- Minimum payment amount
- Active/inactive status

Utilisation status:
- OK (green): less than 50% used
- WARNING (yellow): 50-80% used
- DANGER (red): 80%+ used
