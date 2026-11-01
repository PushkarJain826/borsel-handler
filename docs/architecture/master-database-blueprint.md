# BORSEL HANDLER
## Master Database Architecture & Schema Blueprint
**Version:** 1.0  
**Status:** Architecture design — approved direction, pending implementation  
**Database:** PostgreSQL 16 + TimescaleDB extension  
**Initial exchange:** NSE  
**Future exchange support:** BSE and other exchanges

---

# 1. Project Overview

Borsel Handler is a modular financial data collection and management platform focused initially on Indian stock market data.

Its primary responsibility is to collect, verify, normalize, version and store financial information from exchange sources.

### Initial data scope

1. Daily equity market data.
2. Index historical data.
3. Delivery statistics.
4. Corporate actions.
5. Company financial results.
6. Financial statements.
7. Financial ratios.
8. Shareholding patterns.
9. Instrument and exchange reference data.

### Historical coverage

- Target: Five years of historical data.
- Daily incremental collection.
- Historical backfill with missing-date and holiday handling.
- Preserve corrected reports and historical revisions.

### Important source-format consideration

NSE's Bhavcopy format changed on July 8, 2024, introducing the CM-UDiFF format.

The ingestion architecture must support separate parsers for different source-format versions while normalizing their output into common internal data models.

---

# 2. Database Architecture

## 2.1 Logical database schemas

The database will contain seven logical schemas.

| Schema | Responsibility | Proposed tables |
|---|---|---:|
| reference | Exchanges, companies, instruments and listings | 7 |
| market | Equity prices, indices and delivery data | 8 |
| corporate | Dividends, splits, bonuses, rights, mergers and buybacks | 9 |
| ingestion | Sources, reports, files, processing and execution | 7 |
| quality | Validation, rejected records and quality metrics | 4 |
| fundamentals | Financial results, statements, ratios and shareholding | 11 |
| system | Configuration, scheduling, parsers and audit logs | 5 |
| **Total** | | **51** |

Table counts represent the proposed design after adding the versioning refinements. They may change during detailed model review.

## 2.2 Database conventions

| Item | Standard |
|---|---|
| Primary keys | UUID |
| Foreign keys | UUID |
| Date and time | DATE / TIMESTAMPTZ |
| Financial values | NUMERIC |
| Percentages | NUMERIC |
| Large quantities | BIGINT |
| Flexible metadata | JSONB |
| Boolean fields | BOOLEAN |
| Currency | CHAR(3) |
| Country | CHAR(2) |
| Timezone | IANA timezone identifier |

### Naming conventions

- Table names: `snake_case`, plural where appropriate.
- Column names: `snake_case`.
- Primary key: `id`.
- Foreign key: `<referenced_entity>_id`.
- Creation timestamp: `created_at`.
- Modification timestamp: `updated_at`.
- Version number: `version_number`.
- Current version indicator: `is_current`.

### General database rules

1. Avoid hard deletion of historical financial data.
2. Use soft deactivation where records should no longer be used.
3. Preserve source provenance.
4. Use explicit foreign keys.
5. Add indexes to frequently queried foreign keys and date columns.
6. Use database constraints for important integrity rules.
7. Do not use floating-point data types for financial values.
8. Use UTC timestamps for stored event times, while preserving exchange-local trading dates.

---

# 3. REFERENCE SCHEMA

**Purpose:** Maintain the identity of companies, instruments, exchanges and listings.

This schema is foundational because market and corporate data must connect to stable internal identifiers rather than temporary exchange symbols.

## 3.1 `reference.exchanges`

Stores supported stock exchanges.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| code | VARCHAR(20) | UNIQUE, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| country | CHAR(2) | NOT NULL |
| timezone | VARCHAR(50) | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Examples: NSE, BSE.

## 3.2 `reference.companies`

Stores company-level information.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(255) | NOT NULL |
| legal_name | VARCHAR(255) | NULL |
| country | CHAR(2) | NOT NULL |
| website | TEXT | NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

## 3.3 `reference.company_identifiers`

Stores identifiers associated with companies.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → companies |
| identifier_type | VARCHAR(30) | NOT NULL |
| identifier_value | VARCHAR(100) | NOT NULL |
| valid_from | DATE | NOT NULL |
| valid_to | DATE | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Examples: CIN, LEI.

## 3.4 `reference.instruments`

Represents securities issued by companies.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → companies |
| name | VARCHAR(255) | NOT NULL |
| instrument_type | VARCHAR(50) | NOT NULL |
| currency | CHAR(3) | NOT NULL |
| face_value | NUMERIC(20,6) | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Initial instrument types:

- EQUITY
- PREFERENCE_SHARE
- BOND
- DEBENTURE
- ETF
- OTHER

## 3.5 `reference.instrument_listings`

Represents an instrument's listing on an exchange.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| instrument_id | UUID | FK → instruments |
| exchange_id | UUID | FK → exchanges |
| listing_date | DATE | NULL |
| delisting_date | DATE | NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Unique constraint: `(instrument_id, exchange_id)`.

## 3.6 `reference.listing_history`

Preserves historical listing information.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| listing_id | UUID | FK → instrument_listings |
| symbol | VARCHAR(100) | NULL |
| series | VARCHAR(20) | NULL |
| security_code | VARCHAR(50) | NULL |
| lot_size | NUMERIC(20,6) | NULL |
| tick_size | NUMERIC(20,6) | NULL |
| valid_from | DATE | NOT NULL |
| valid_to | DATE | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Validity convention:

- `valid_from` is inclusive.
- `valid_to` is exclusive.
- NULL `valid_to` means the record is currently valid.

Overlapping validity periods for the same listing must be prevented.

## 3.7 `reference.instrument_identifiers`

Stores external security identifiers.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| instrument_id | UUID | FK → instruments |
| identifier_type | VARCHAR(30) | NOT NULL |
| identifier_value | VARCHAR(100) | NOT NULL |
| valid_from | DATE | NOT NULL |
| valid_to | DATE | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

ISIN is an important external identifier, but it will not be used as the internal primary key.

### Reference schema relationships

- One company can issue multiple instruments.
- One instrument can have listings on multiple exchanges.
- One listing can have multiple historical symbol records.
- One company can have multiple identifiers.
- One instrument can have multiple external identifiers over time.

---

# 4. MARKET SCHEMA

**Purpose:** Store historical and daily market observations.

Initial scope is daily end-of-day data.

Intraday data is outside the initial implementation scope.

## 4.1 `market.daily_observations`

Logical identity of an equity observation.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| listing_id | UUID | FK → reference.instrument_listings |
| trading_date | DATE | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Unique constraint: `(listing_id, trading_date)`.

## 4.2 `market.daily_observation_versions`

Stores versions of daily market observations.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| observation_id | UUID | FK → daily_observations |
| version_number | INTEGER | NOT NULL |
| open_price | NUMERIC(20,6) | NULL |
| high_price | NUMERIC(20,6) | NULL |
| low_price | NUMERIC(20,6) | NULL |
| close_price | NUMERIC(20,6) | NULL |
| previous_close | NUMERIC(20,6) | NULL |
| last_price | NUMERIC(20,6) | NULL |
| vwap | NUMERIC(20,6) | NULL |
| traded_quantity | BIGINT | NULL |
| traded_value | NUMERIC(24,6) | NULL |
| number_of_trades | BIGINT | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Constraints:

- Unique `(observation_id, version_number)`.
- Only one current version per observation.
- Nonnegative prices, values and quantities where applicable.
- High must be greater than or equal to low, open and close.
- Low must be less than or equal to open and close.

## 4.3 `market.indices`

Stores index reference information.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(150) | NOT NULL |
| index_code | VARCHAR(100) | NOT NULL |
| index_type | VARCHAR(50) | NOT NULL |
| currency | CHAR(3) | NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

Examples: NIFTY 50, NIFTY BANK and sectoral indices.

## 4.4 `market.index_listings`

Connects indices to exchanges.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| index_id | UUID | FK → indices |
| exchange_id | UUID | FK → reference.exchanges |
| exchange_index_code | VARCHAR(100) | NULL |
| valid_from | DATE | NOT NULL |
| valid_to | DATE | NULL |

## 4.5 `market.index_observations`

Logical identity of an index observation.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| index_listing_id | UUID | FK → index_listings |
| trading_date | DATE | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Unique constraint: `(index_listing_id, trading_date)`.

## 4.6 `market.index_observation_versions`

Stores index observation revisions.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| observation_id | UUID | FK → index_observations |
| version_number | INTEGER | NOT NULL |
| open_value | NUMERIC(20,6) | NULL |
| high_value | NUMERIC(20,6) | NULL |
| low_value | NUMERIC(20,6) | NULL |
| close_value | NUMERIC(20,6) | NULL |
| previous_close | NUMERIC(20,6) | NULL |
| points_change | NUMERIC(20,6) | NULL |
| percentage_change | NUMERIC(12,6) | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Unique `(observation_id, version_number)` and one-current-version constraint.

## 4.7 `market.delivery_observations`

Logical identity of delivery statistics.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| listing_id | UUID | FK → reference.instrument_listings |
| trading_date | DATE | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Unique `(listing_id, trading_date)`.

## 4.8 `market.delivery_observation_versions`

Stores delivery statistics revisions.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| observation_id | UUID | FK → delivery_observations |
| version_number | INTEGER | NOT NULL |
| deliverable_quantity | BIGINT | NULL |
| deliverable_percentage | NUMERIC(12,6) | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Unique `(observation_id, version_number)` and one-current-version constraint.

### Market schema rules

- Delivery statistics are separate from daily equity observations.
- Every corrected observation receives a new version.
- Existing versions are never overwritten.
- The latest accepted version is marked current.
- Source provenance is recorded through `source_run_id`.
- Percentage semantics and exact source mappings must be validated against NSE reports during parser design.

---

# 5. CORPORATE SCHEMA

**Purpose:** Store corporate actions and their revisions.

The design uses a central action table, instrument mapping, action versions and action-specific detail tables.

## 5.1 `corporate.corporate_actions`

Stores common action information.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → reference.companies |
| action_type | VARCHAR(50) | NOT NULL |
| announcement_date | DATE | NULL |
| status | VARCHAR(30) | NOT NULL |
| description | TEXT | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

## 5.2 `corporate.action_instruments`

Maps actions to affected instruments.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| action_id | UUID | FK → corporate_actions |
| instrument_id | UUID | FK → reference.instruments |
| role | VARCHAR(30) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Roles can include AFFECTED, ACQUIRING and TARGET.

## 5.3 `corporate.action_versions`

Preserves revisions of corporate-action information.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| action_id | UUID | FK → corporate_actions |
| version_number | INTEGER | NOT NULL |
| announcement_date | DATE | NULL |
| status | VARCHAR(30) | NOT NULL |
| description | TEXT | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Unique `(action_id, version_number)` and one-current-version constraint.

## 5.4 `corporate.dividend_details`

| Column | Type |
|---|---|
| id | UUID PK |
| action_version_id | UUID FK |
| dividend_type | VARCHAR(30) |
| dividend_amount | NUMERIC(20,6) |
| currency | CHAR(3) |
| record_date | DATE |
| ex_date | DATE |
| payment_date | DATE |

## 5.5 `corporate.split_details`

| Column | Type |
|---|---|
| id | UUID PK |
| action_version_id | UUID FK |
| old_face_value | NUMERIC(20,6) |
| new_face_value | NUMERIC(20,6) |
| record_date | DATE |
| ex_date | DATE |
| effective_date | DATE |

## 5.6 `corporate.bonus_details`

| Column | Type |
|---|---|
| id | UUID PK |
| action_version_id | UUID FK |
| bonus_numerator | INTEGER |
| bonus_denominator | INTEGER |
| record_date | DATE |
| ex_date | DATE |
| allotment_date | DATE |

## 5.7 `corporate.rights_issue_details`

| Column | Type |
|---|---|
| id | UUID PK |
| action_version_id | UUID FK |
| rights_numerator | INTEGER |
| rights_denominator | INTEGER |
| issue_price | NUMERIC(20,6) |
| currency | CHAR(3) |
| record_date | DATE |
| ex_date | DATE |
| subscription_start_date | DATE |
| subscription_end_date | DATE |
| allotment_date | DATE |

## 5.8 `corporate.merger_details`

| Column | Type |
|---|---|
| id | UUID PK |
| action_version_id | UUID FK |
| consideration_type | VARCHAR(30) |
| exchange_numerator | NUMERIC(20,6) |
| exchange_denominator | NUMERIC(20,6) |
| effective_date | DATE |
| completion_date | DATE |
| cash_consideration | NUMERIC(20,6) |
| currency | CHAR(3) |

The involved companies and instruments are identified using `action_instruments`.

## 5.9 `corporate.buyback_details`

| Column | Type |
|---|---|
| id | UUID PK |
| action_version_id | UUID FK |
| buyback_method | VARCHAR(30) |
| buyback_price | NUMERIC(20,6) |
| currency | CHAR(3) |
| maximum_shares | BIGINT |
| maximum_amount | NUMERIC(24,6) |
| record_date | DATE |
| opening_date | DATE |
| closing_date | DATE |

### Corporate action rules

- Preserve revisions and cancellations.
- Never overwrite old versions.
- A corporate action may affect multiple instruments.
- Announcement, ex-date, record date, effective date, payment date and allotment date remain separate.
- Ratios are stored numerically.
- Additional action types can be introduced without redesigning the entire schema.

Future action types include demergers, delisting, share consolidation and preferential allotments.

Their dedicated detail tables can be introduced when reliable source data is available.

---

# 6. INGESTION SCHEMA

**Purpose:** Manage the complete data collection lifecycle.

The ingestion schema is responsible for discovering, downloading, verifying, processing and tracking source reports.

## 6.1 `ingestion.data_sources`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| code | VARCHAR(50) | UNIQUE, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| exchange_id | UUID | FK → reference.exchanges |
| source_type | VARCHAR(30) | NOT NULL |
| base_url | TEXT | NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

## 6.2 `ingestion.datasets`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| code | VARCHAR(50) | UNIQUE, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| description | TEXT | NULL |
| frequency | VARCHAR(20) | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

Initial datasets:

- EQUITY_EOD
- INDEX_EOD
- EQUITY_DELIVERY
- CORPORATE_ACTIONS
- QUARTERLY_RESULTS
- ANNUAL_FINANCIALS
- SHAREHOLDING_PATTERNS

## 6.3 `ingestion.source_reports`

Tracks expected or discovered reports.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| data_source_id | UUID | FK → data_sources |
| dataset_id | UUID | FK → datasets |
| trading_date | DATE | NULL |
| report_url | TEXT | NULL |
| report_format | VARCHAR(30) | NULL |
| source_format_version | VARCHAR(50) | NULL |
| status | VARCHAR(30) | NOT NULL |
| discovered_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

A report may be discovered, downloaded, missing or failed.

## 6.4 `ingestion.files`

Tracks downloaded and archived source files.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| source_report_id | UUID | FK → source_reports |
| file_name | VARCHAR(255) | NOT NULL |
| storage_path | TEXT | NOT NULL |
| file_format | VARCHAR(30) | NOT NULL |
| file_size_bytes | BIGINT | NULL |
| checksum_sha256 | VARCHAR(64) | NOT NULL |
| downloaded_at | TIMESTAMPTZ | NOT NULL |
| verification_status | VARCHAR(30) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Corrected source files must be stored as new file records. Old archived files must remain intact.

## 6.5 `ingestion.ingestion_runs`

Central execution and provenance record.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| dataset_id | UUID | FK → datasets |
| source_id | UUID | FK → data_sources |
| run_type | VARCHAR(30) | NOT NULL |
| status | VARCHAR(30) | NOT NULL |
| start_date | DATE | NULL |
| end_date | DATE | NULL |
| started_at | TIMESTAMPTZ | NULL |
| completed_at | TIMESTAMPTZ | NULL |
| records_processed | BIGINT | DEFAULT 0 |
| records_failed | BIGINT | DEFAULT 0 |
| error_message | TEXT | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Run types:

- BACKFILL
- DAILY
- RETRY
- REPROCESS

Statuses:

- PENDING
- RUNNING
- COMPLETED
- FAILED
- PARTIAL

## 6.6 `ingestion.file_processing`

Tracks processing of individual files.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| file_id | UUID | FK → files |
| ingestion_run_id | UUID | FK → ingestion_runs |
| parser_name | VARCHAR(100) | NOT NULL |
| parser_version | VARCHAR(50) | NOT NULL |
| status | VARCHAR(30) | NOT NULL |
| records_read | BIGINT | DEFAULT 0 |
| records_accepted | BIGINT | DEFAULT 0 |
| records_rejected | BIGINT | DEFAULT 0 |
| error_details | TEXT | NULL |
| started_at | TIMESTAMPTZ | NULL |
| completed_at | TIMESTAMPTZ | NULL |

## 6.7 `ingestion.job_executions`

Tracks Celery task executions.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| ingestion_run_id | UUID | FK → ingestion_runs |
| celery_task_id | VARCHAR(100) | NOT NULL |
| task_name | VARCHAR(150) | NOT NULL |
| status | VARCHAR(30) | NOT NULL |
| attempt_number | INTEGER | NOT NULL |
| started_at | TIMESTAMPTZ | NULL |
| completed_at | TIMESTAMPTZ | NULL |
| error_message | TEXT | NULL |

PostgreSQL remains the authoritative source of ingestion status. Celery's internal task state is supplementary.

### Ingestion rules

1. Preserve original downloaded files.
2. Use SHA-256 for file integrity and duplicate detection.
3. Preserve corrected source files.
4. Record parser name and version.
5. Track download and parsing failures separately.
6. Make processing idempotent.
7. Support historical backfills and incremental daily collection.
8. Track missing expected reports.
9. Link every accepted financial observation version to its ingestion run.

---

# 7. QUALITY SCHEMA

**Purpose:** Validate collected information and maintain data quality history.

Validation operates at three levels:

- File-level.
- Record-level.
- Dataset-level.

## 7.1 `quality.validation_rules`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| code | VARCHAR(100) | UNIQUE, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| description | TEXT | NULL |
| dataset_id | UUID | FK → ingestion.datasets, NULL |
| validation_level | VARCHAR(30) | NOT NULL |
| severity | VARCHAR(20) | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

## 7.2 `quality.validation_results`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| rule_id | UUID | FK → validation_rules |
| ingestion_run_id | UUID | FK → ingestion.ingestion_runs |
| file_processing_id | UUID | FK → ingestion.file_processing, NULL |
| status | VARCHAR(20) | NOT NULL |
| records_checked | BIGINT | DEFAULT 0 |
| records_passed | BIGINT | DEFAULT 0 |
| records_failed | BIGINT | DEFAULT 0 |
| message | TEXT | NULL |
| executed_at | TIMESTAMPTZ | NOT NULL |

## 7.3 `quality.rejected_records`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| file_processing_id | UUID | FK → ingestion.file_processing |
| rule_id | UUID | FK → validation_rules, NULL |
| row_number | BIGINT | NULL |
| raw_record | JSONB | NOT NULL |
| error_code | VARCHAR(100) | NOT NULL |
| error_message | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Rejected records will be retained permanently initially.

A retention or archival policy may be introduced later if storage requirements change.

## 7.4 `quality.dataset_quality_snapshots`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| dataset_id | UUID | FK → ingestion.datasets |
| ingestion_run_id | UUID | FK → ingestion.ingestion_runs, NULL |
| snapshot_date | DATE | NOT NULL |
| total_records | BIGINT | NOT NULL |
| valid_records | BIGINT | NOT NULL |
| rejected_records | BIGINT | NOT NULL |
| completeness_percentage | NUMERIC(7,4) | NULL |
| validity_percentage | NUMERIC(7,4) | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

### Quality rules

- Validation rules must be configurable.
- Severity and rejection behavior are distinct concepts.
- A rule may reject one record or an entire file.
- Missing required columns can stop file processing.
- An unknown symbol may reject only the affected record.
- Warnings need not reject data.
- Rejected rows must retain original source content and error details.
- Quality snapshots must be historical.

---

# 8. FUNDAMENTALS SCHEMA

**Purpose:** Store company financial information.

Initial datasets:

- Quarterly results.
- Half-yearly results.
- Annual results.
- Profit and loss statements.
- Balance sheets.
- Cash flow statements.
- Financial ratios.
- Shareholding patterns.

Standalone and consolidated financial information must be stored separately.

Financial results and statements must support corrected and restated versions.

## 8.1 `fundamentals.reporting_periods`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → reference.companies |
| fiscal_year | VARCHAR(10) | NOT NULL |
| period_type | VARCHAR(20) | NOT NULL |
| period_number | SMALLINT | NULL |
| period_start_date | DATE | NOT NULL |
| period_end_date | DATE | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.2 `fundamentals.financial_results`

Logical identity of a company's financial result.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → reference.companies |
| reporting_period_id | UUID | FK → reporting_periods |
| reporting_basis | VARCHAR(20) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.3 `fundamentals.financial_result_versions`

Stores actual reported values and revisions.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| financial_result_id | UUID | FK → financial_results |
| version_number | INTEGER | NOT NULL |
| revenue | NUMERIC(24,6) | NULL |
| total_income | NUMERIC(24,6) | NULL |
| expenses | NUMERIC(24,6) | NULL |
| operating_profit | NUMERIC(24,6) | NULL |
| interest_expense | NUMERIC(24,6) | NULL |
| depreciation | NUMERIC(24,6) | NULL |
| profit_before_tax | NUMERIC(24,6) | NULL |
| tax_expense | NUMERIC(24,6) | NULL |
| profit_after_tax | NUMERIC(24,6) | NULL |
| earnings_per_share | NUMERIC(20,6) | NULL |
| currency | CHAR(3) | NOT NULL |
| publication_date | DATE | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.4 `fundamentals.financial_statements`

Logical identity of a financial statement.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → reference.companies |
| reporting_period_id | UUID | FK → reporting_periods |
| statement_type | VARCHAR(30) | NOT NULL |
| reporting_basis | VARCHAR(20) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Statement types:

- PROFIT_LOSS
- BALANCE_SHEET
- CASH_FLOW

## 8.5 `fundamentals.financial_statement_versions`

Stores revisions of financial statements.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| statement_id | UUID | FK → financial_statements |
| version_number | INTEGER | NOT NULL |
| currency | CHAR(3) | NOT NULL |
| publication_date | DATE | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.6 `fundamentals.financial_statement_items`

Stores individual statement line items.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| statement_version_id | UUID | FK → financial_statement_versions |
| item_code | VARCHAR(100) | NOT NULL |
| item_name | VARCHAR(255) | NOT NULL |
| item_value | NUMERIC(24,6) | NOT NULL |
| unit | VARCHAR(30) | NULL |
| display_order | INTEGER | NULL |

This flexible structure avoids creating hundreds of columns for every possible statement item.

## 8.7 `fundamentals.financial_ratios`

Logical identity of a financial ratio for a company and reporting period.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → reference.companies |
| reporting_period_id | UUID | FK → reporting_periods |
| reporting_basis | VARCHAR(20) | NOT NULL |
| ratio_code | VARCHAR(100) | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.8 `fundamentals.financial_ratio_versions`

Stores reported or calculated ratio values.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| financial_ratio_id | UUID | FK → financial_ratios |
| version_number | INTEGER | NOT NULL |
| ratio_value | NUMERIC(20,6) | NOT NULL |
| calculation_source | VARCHAR(30) | NOT NULL |
| methodology_version | VARCHAR(50) | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs, NULL |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

`calculation_source` distinguishes REPORTED and CALCULATED values.

For internally calculated ratios, methodology version should identify the calculation logic used.

## 8.9 `fundamentals.shareholding_patterns`

Logical identity of a shareholding report.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| company_id | UUID | FK → reference.companies |
| reporting_period_id | UUID | FK → reporting_periods |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.10 `fundamentals.shareholding_pattern_versions`

Stores revisions to shareholding information.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| shareholding_pattern_id | UUID | FK → shareholding_patterns |
| version_number | INTEGER | NOT NULL |
| total_shares | BIGINT | NULL |
| publication_date | DATE | NULL |
| source_run_id | UUID | FK → ingestion.ingestion_runs |
| is_current | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 8.11 `fundamentals.shareholding_categories`

Stores category-level holdings for a particular version.

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| shareholding_version_id | UUID | FK → shareholding_pattern_versions |
| category_code | VARCHAR(50) | NOT NULL |
| shares_held | BIGINT | NOT NULL |
| percentage_held | NUMERIC(12,6) | NULL |

Examples:

- PROMOTER
- FII
- DII
- PUBLIC

### Fundamentals rules

- Preserve standalone and consolidated results separately.
- Reporting period and publication date must remain distinct.
- Preserve corrected and restated versions.
- Store line items flexibly.
- Preserve reported and calculated ratios separately.
- Record methodology versions for calculated ratios.
- Every sourced version must have provenance.
- Shareholding categories belong to a specific shareholding version.

---

# 9. SYSTEM SCHEMA

**Purpose:** Manage system configuration, parser registration, scheduling and administrative audit history.

## 9.1 `system.dataset_configurations`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| dataset_id | UUID | FK → ingestion.datasets |
| source_id | UUID | FK → ingestion.data_sources |
| is_enabled | BOOLEAN | DEFAULT TRUE |
| collection_frequency | VARCHAR(30) | NOT NULL |
| collection_time | TIME | NULL |
| timezone | VARCHAR(50) | NOT NULL |
| retry_limit | INTEGER | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

## 9.2 `system.parser_registry`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| parser_name | VARCHAR(100) | NOT NULL |
| dataset_id | UUID | FK → ingestion.datasets |
| source_format_version | VARCHAR(50) | NOT NULL |
| parser_version | VARCHAR(50) | NOT NULL |
| module_path | VARCHAR(255) | NOT NULL |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMPTZ | NOT NULL |

## 9.3 `system.scheduled_jobs`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| job_name | VARCHAR(150) | NOT NULL |
| task_name | VARCHAR(150) | NOT NULL |
| dataset_id | UUID | FK → ingestion.datasets, NULL |
| cron_expression | VARCHAR(100) | NOT NULL |
| timezone | VARCHAR(50) | NOT NULL |
| is_enabled | BOOLEAN | DEFAULT TRUE |
| last_run_at | TIMESTAMPTZ | NULL |
| next_run_at | TIMESTAMPTZ | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

PostgreSQL stores the scheduling configuration. Celery Beat reads and executes the configured schedules.

Only one Celery Beat instance will run initially.

## 9.4 `system.application_settings`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| setting_key | VARCHAR(150) | UNIQUE, NOT NULL |
| setting_value | JSONB | NOT NULL |
| description | TEXT | NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Examples:

- Default backfill period.
- Maximum concurrent downloads.
- File size limits.
- Retry delay.
- Data retention settings.

Secrets, passwords and API keys must remain outside this table, in environment variables or a secrets manager.

## 9.5 `system.audit_logs`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| actor | VARCHAR(150) | NOT NULL |
| action | VARCHAR(100) | NOT NULL |
| entity_type | VARCHAR(100) | NOT NULL |
| entity_id | UUID | NULL |
| old_values | JSONB | NULL |
| new_values | JSONB | NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

Records important administrative and configuration changes.

Examples:

- Dataset enabled or disabled.
- Parser version changed.
- Scheduled job modified.
- Validation rule disabled.
- Application configuration changed.

### User management

Initial deployment uses a single administrator.

Full multi-user authentication and role management are deferred.

The architecture should not assume that all future actions will be performed by the same administrator. The audit actor field can identify the system or administrator initially and later be connected to user identities.

---

# 10. CROSS-SCHEMA RELATIONSHIPS

The most important relationships are listed below.

| Parent | Child | Relationship |
|---|---|---|
| reference.companies | reference.instruments | One-to-many |
| reference.instruments | reference.instrument_listings | One-to-many |
| reference.exchanges | reference.instrument_listings | One-to-many |
| reference.instrument_listings | reference.listing_history | One-to-many |
| reference.instrument_listings | market.daily_observations | One-to-many |
| reference.instrument_listings | market.delivery_observations | One-to-many |
| market.daily_observations | market.daily_observation_versions | One-to-many |
| market.index_observations | market.index_observation_versions | One-to-many |
| market.delivery_observations | market.delivery_observation_versions | One-to-many |
| corporate.corporate_actions | corporate.action_versions | One-to-many |
| corporate.corporate_actions | corporate.action_instruments | One-to-many |
| ingestion.ingestion_runs | market observation versions | One-to-many |
| ingestion.ingestion_runs | corporate.action_versions | One-to-many |
| ingestion.ingestion_runs | fundamentals versions | One-to-many |
| ingestion.files | ingestion.file_processing | One-to-many |
| ingestion.ingestion_runs | ingestion.job_executions | One-to-many |
| ingestion.file_processing | quality.rejected_records | One-to-many |
| ingestion.datasets | quality.validation_rules | One-to-many |
| ingestion.datasets | system.dataset_configurations | One-to-many |
| fundamentals.reporting_periods | fundamentals financial records | One-to-many |

### Cross-schema foreign keys

The following references must be added during implementation:

- Market versions → `ingestion.ingestion_runs`.
- Corporate action versions → `ingestion.ingestion_runs`.
- Fundamentals versions → `ingestion.ingestion_runs`.

Because ingestion run records must exist before data can reference them, implementation and migration ordering must respect these dependencies.

---

# 11. VERSIONING AND HISTORICAL DATA STRATEGY

Versioning is a central requirement.

We must preserve corrections rather than overwrite historical records.

## 11.1 Logical record and version record

Example:

A listing has a daily observation for October 20.

Original NSE report:

| Version | Close price | Current |
|---|---:|---|
| 1 | ₹1,250 | No |

NSE later publishes a correction:

| Version | Close price | Current |
|---|---:|---|
| 1 | ₹1,250 | No |
| 2 | ₹1,252 | Yes |

The logical observation remains the same. A new version is inserted.

## 11.2 Versioning requirements

Every versioned entity should have:

- Logical record identifier.
- Version number.
- Source run reference, where applicable.
- Creation timestamp.
- Current-version indicator.
- Unique logical-record/version-number constraint.
- Partial unique index allowing only one current version.

Version changes must be performed transactionally:

1. Insert new version.
2. Mark previous current version as non-current.
3. Mark new version as current.
4. Commit the transaction.

## 11.3 Versioned entities

- Equity observations.
- Index observations.
- Delivery observations.
- Corporate actions.
- Financial results.
- Financial statements.
- Financial ratios.
- Shareholding patterns.

For calculated ratios, methodology changes should also be traceable.

---

# 12. FILE STORAGE AND PROVENANCE

Database records alone are not sufficient for reproducible financial data collection.

Borsel Handler must preserve source files and their processing history.

## 12.1 Storage layout

```text
storage/
├── raw/
│   ├── nse/
│   │   ├── bhavcopy/
│   │   │   ├── legacy/
│   │   │   └── udiff/
│   │   ├── indices/
│   │   ├── delivery/
│   │   └── corporate_actions/
│   └── bse/
│
├── extracted/
│
├── processed/
│
├── quarantine/
│
└── logs/
```

## 12.2 Storage responsibilities

| Directory | Responsibility |
|---|---|
| raw | Original downloaded files |
| extracted | Extracted file contents and intermediate outputs |
| processed | Normalized processing outputs |
| quarantine | Invalid or suspicious files |
| logs | Operational logs |

Raw files must remain unchanged.

Extracted and processed files should be regenerable from original files and the relevant parser version.

## 12.3 Provenance chain

Every accepted financial observation should be traceable through this chain:

```text
Financial observation version
        |
        v
Ingestion run
        |
        v
File processing
        |
        v
Downloaded file
        |
        v
Source report
        |
        v
Data source
```

This is essential for auditing, debugging and historical reprocessing.

---

# 13. VALIDATION AND DATA QUALITY POLICY

Validation behavior must be configurable by rule.

| Example | Recommended behavior |
|---|---|
| Missing required CSV columns | Reject entire file |
| Invalid file format | Reject entire file |
| Unknown security symbol | Reject affected record |
| Negative price | Reject affected record |
| High lower than low | Reject affected record |
| Unusual price movement | Warning, investigate |
| Missing expected report | Record missing report status |

The system should distinguish between:

- INFO
- WARNING
- ERROR
- CRITICAL

Severity alone does not determine whether the file or record is rejected. The validation policy should specify the rejection scope.

Rejected records will be retained permanently initially.

---

# 14. INDEXING AND CONSTRAINT STRATEGY

The following indexes and constraints should be part of the implementation plan.

## 14.1 Reference schema

- Unique exchange code.
- Index company foreign keys.
- Index instrument foreign keys.
- Index exchange foreign keys.
- Index current and historical symbols.
- Index identifier type and value.
- Prevent overlapping identifier validity periods where applicable.
- Prevent overlapping listing-history validity periods.

## 14.2 Market schema

Recommended indexes:

- `(listing_id, trading_date)`
- `(trading_date)`
- `(observation_id, version_number)`
- Partial unique index on current versions.
- `(index_listing_id, trading_date)`

## 14.3 Corporate schema

Recommended indexes:

- `(company_id, action_type)`
- `(announcement_date)`
- `(action_id, version_number)`
- `(instrument_id)`
- Partial unique index on current action versions.

## 14.4 Ingestion schema

Recommended indexes:

- `(dataset_id, status)`
- `(data_source_id, trading_date)`
- `(source_report_id)`
- `(checksum_sha256)`
- `(ingestion_run_id, status)`
- `(celery_task_id)`

## 14.5 Quality schema

Recommended indexes:

- `(ingestion_run_id)`
- `(rule_id, status)`
- `(file_processing_id)`
- `(created_at)`

## 14.6 Fundamentals schema

Recommended indexes:

- `(company_id, reporting_period_id)`
- `(reporting_period_id)`
- `(financial_result_id, version_number)`
- `(statement_id, version_number)`
- `(shareholding_pattern_id, version_number)`
- Partial unique indexes for current versions.

## 14.7 System schema

Recommended indexes:

- `(dataset_id, is_enabled)`
- `(is_enabled)`
- `(created_at)`
- `(entity_type, entity_id)`

### Important constraint note

A normal unique constraint cannot prevent all overlapping date ranges.

For historical validity periods, PostgreSQL range types and exclusion constraints should be evaluated during SQLAlchemy model design.

---

# 15. PERFORMANCE AND SCALABILITY STRATEGY

The initial database will use ordinary PostgreSQL tables.

TimescaleDB will be installed and available, but we will not convert every table into a hypertable.

### Initial approach

- Ordinary relational tables.
- Appropriate indexes.
- Efficient bulk inserts.
- SQLAlchemy 2.x.
- Asynchronous application database access.
- Batch-oriented ingestion.
- Connection pooling.

### Future optimization

Partitioning or TimescaleDB hypertables may be considered when:

- Daily observations grow substantially.
- Date-range queries become slower.
- Database maintenance becomes expensive.
- Historical data volume justifies partition management.

Do not introduce partitioning merely because the data is time-series data.

---

# 16. IMPLEMENTATION TECHNOLOGY

| Component | Technology |
|---|---|
| Backend | Python |
| API | FastAPI |
| ORM | SQLAlchemy 2.x |
| Data validation | Pydantic |
| Database | PostgreSQL 16 |
| Time-series extension | TimescaleDB |
| Migrations | Alembic |
| Background tasks | Celery |
| Scheduler | Celery Beat |
| Broker | Redis |
| Containers | Docker |
| Local orchestration | Docker Compose |

### Database architecture

- One PostgreSQL database.
- Seven logical schemas.
- One shared application database configuration.
- Separate SQLAlchemy model modules.
- Alembic migrations.
- PostgreSQL as the authoritative source for ingestion status and historical records.

### Application architecture

Use a modular monolith.

API, worker and scheduler can use the same application image but run different commands.

No microservices or Kubernetes are required initially.

---

# 17. IMPLEMENTATION ORDER

Do not implement all 51 tables in a single step.

Recommended implementation phases:

| Phase | Scope |
|---|---|
| 1 | Database conventions, UUID handling and schema setup |
| 2 | Reference schema |
| 3 | Ingestion foundation |
| 4 | Market schema |
| 5 | Corporate schema |
| 6 | Quality schema |
| 7 | Fundamentals schema |
| 8 | System schema |
| 9 | Cross-schema constraints and integration tests |

### Phase 1: Reference

Create exchanges, companies, identifiers, instruments, listings and history.

Test company-to-instrument and instrument-to-exchange relationships.

### Phase 2: Ingestion

Create sources, datasets, reports, files, runs, processing and job execution tables.

Test file tracking and ingestion run lifecycle.

### Phase 3: Market

Start with NSE daily equity observations.

Test historical backfill, daily incremental ingestion and corrected report versioning.

### Phase 4 onward

Add the remaining datasets and operational capabilities.

Every phase should have its own migration and tests.

---

# 18. IMPORTANT DESIGN DECISIONS REGISTER

These decisions represent the agreed architectural direction.

| Decision | Selected approach |
|---|---|
| Database | PostgreSQL + TimescaleDB |
| Logical schemas | Seven |
| Primary keys | UUID |
| Historical coverage | Five years |
| Collection strategy | Batch processing |
| Exchange support | NSE initially, BSE-ready |
| Market frequency | Daily EOD initially |
| Data versioning | Preserve corrections |
| Source files | Preserve raw and processed layers |
| Parser architecture | Modular and format-specific |
| Database architecture | Modular monolith |
| Backend | Python + FastAPI |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Background execution | Celery |
| Scheduling | PostgreSQL configuration + Celery Beat |
| Broker | Redis |
| Validation | Configurable rejection scope |
| Rejected records | Permanent retention initially |
| User management | Single administrator initially |
| Audit logs | Important administrative/configuration changes |
| Deployment | Local Docker Compose |
| Partitioning | Deferred until justified |
| Microservices | Not initially |
| Kubernetes | Not initially |

---

# 19. ITEMS REQUIRING DETAILED DESIGN BEFORE IMPLEMENTATION

The master architecture defines the overall structure. The following details should be settled during detailed model and parser design rather than guessed by the coding agent.

1. Exact NSE and BSE source-field mappings.
2. Exact CM-UDiFF and legacy Bhavcopy column mappings.
3. Delivery percentage calculation and source semantics.
4. Corporate-action source-specific fields and action identifiers.
5. Financial statement item taxonomy and units.
6. Financial ratio calculation formulas and methodology versions.
7. Fiscal-year and reporting-period normalization.
8. Historical symbol and ISIN mapping edge cases.
9. Exact parser-to-dataset mapping.
10. Final uniqueness and temporal exclusion constraints.
11. File correction and duplicate-report identification rules.
12. Transaction and bulk-insert strategy for version creation.

These are intentionally left for their respective implementation stages.

---

# 20. FINAL ARCHITECTURE PRINCIPLE

Borsel Handler should maintain a clear distinction between:

- **What the financial entity is:** Reference.
- **What happened in the market:** Market.
- **What corporate event occurred:** Corporate.
- **Where the information came from:** Ingestion.
- **Whether the information is reliable:** Quality.
- **What the company reported financially:** Fundamentals.
- **How the platform operates:** System.

The most important architectural principle is traceability.

For any financial value stored in Borsel Handler, we should eventually be able to identify its source, original file, parser version, processing run, validation outcome and historical revisions.

That is the foundation of a reliable financial data platform.

**End of Master Database Blueprint — Version 1.0**