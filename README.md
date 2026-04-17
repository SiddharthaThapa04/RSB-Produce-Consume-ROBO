# Traffic Data Work Item Automation

> An end-to-end RPA pipeline that downloads, processes, and validates global road traffic fatality data — then routes it to an external sales system using Robocorp Work Items.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
  - [Producer Task](#producer-task-produce_traffic_data)
  - [Consumer Task](#consumer-task-process_traffic_data)
- [Work Item Payload Schema](#work-item-payload-schema)
- [Error Handling](#error-handling)
- [API Reference](#api-reference)
- [Key Functions](#key-functions)
- [Getting Started](#getting-started)
- [Future Improvements](#future-improvements)
- [Author](#author)

---

## Overview

This automation implements a **Producer–Consumer pattern** using the Robocorp Work Items framework. It ingests raw JSON traffic statistics published by the WHO, applies filtering and deduplication logic, and pushes the cleaned records to an external insurance sales system API.

The workflow is split into two independently runnable tasks:

| Task                   | Role         | Description                                                    |
| ---------------------- | ------------ | -------------------------------------------------------------- |
| `produce_traffic_data` | **Producer** | Downloads, filters, and packages traffic records as work items |
| `process_traffic_data` | **Consumer** | Validates each work item and posts it to the sales system API  |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     PRODUCER TASK                       │
│                                                         │
│  [JSON Dataset URL]                                     │
│         │                                               │
│         ▼                                               │
│  Download & Parse JSON                                  │
│         │                                               │
│         ▼                                               │
│  Convert to Table Structure                             │
│         │                                               │
│         ▼                                               │
│  Filter: rate < 5.0 & gender == BTSX                    │
│         │                                               │
│         ▼                                               │
│  Sort by Year (desc) → Deduplicate by Country           │
│         │                                               │
│         ▼                                               │
│  Generate Work Item Payloads                            │
│         │                                               │
│         ▼                                               │
│  [Output Work Items Queue] ──────────────────┐          │
└──────────────────────────────────────────────┼──────────┘
                                               │
                                               ▼
┌─────────────────────────────────────────────────────────┐
│                     CONSUMER TASK                       │
│                                                         │
│  [Input Work Items Queue]                               │
│         │                                               │
│         ▼                                               │
│  Validate Payload (country code = 3 chars)              │
│         │                                               │
│    ┌────┴────┐                                          │
│  VALID    INVALID                                       │
│    │          │                                         │
│    ▼          ▼                                         │
│  POST API   FAIL (BUSINESS ERROR)                       │
│    │                                                    │
│  ┌─┴──┐                                                 │
│ 200  Error                                              │
│  │     │                                                │
│ DONE  FAIL (APPLICATION ERROR)                          │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component                         | Purpose                                          |
| --------------------------------- | ------------------------------------------------ |
| [Robocorp](https://robocorp.com/) | RPA framework and work item orchestration        |
| Python 3                          | Core scripting language                          |
| `RPA.HTTP`                        | HTTP requests for downloading the dataset        |
| `RPA.JSON`                        | JSON parsing and manipulation                    |
| `RPA.Tables`                      | Tabular data filtering, sorting, and grouping    |
| `robocorp-workitems`              | Producer–Consumer work item lifecycle management |
| `requests`                        | External API calls to the sales system           |

---

## Project Structure

```
.
├── tasks.py              # Main producer and consumer task definitions
├── output/
│   └── traffic.json      # Downloaded raw JSON dataset (generated at runtime)
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

---

## How It Works

### Producer Task: `produce_traffic_data`

The producer downloads and processes a WHO road traffic dataset, applying business rules before packaging results as work items.

**Step-by-step:**

**1. Download Dataset**

Fetches the raw JSON from:

```
https://github.com/robocorp/inhuman-insurance-inc/raw/main/RS_198.json
```

Saved locally to `output/traffic.json`.

**2. Load into Table**

Converts the raw JSON array into an `RPA.Tables` table for efficient filtering and sorting.

**3. Filter & Sort**

Applies two filters:

- `NumericValue < 5.0` — keeps only low-rate countries
- `Dim1 == "BTSX"` — keeps only "both sexes" gender dimension

Then sorts by `TimeDim` in **descending** order (most recent year first).

**4. Deduplicate by Country**

Extracts only the **latest record per country**, ensuring no duplicates enter the work item queue.

**5. Create Work Item Payloads**

Transforms each row into a structured payload (see [schema below](#work-item-payload-schema)).

**6. Save as Output Work Items**

Persists each payload as an individual work item, making them available for the consumer task.

---

### Consumer Task: `process_traffic_data`

The consumer iterates over all queued work items, validates them, and sends valid records to the sales system API.

**Step-by-step:**

**1. Iterate Work Items**

Reads all input work items from the queue generated by the producer.

**2. Validate Payload**

Checks that the `country` field is exactly **3 characters** long. Invalid items are immediately failed with a `BUSINESS` error.

**3. POST to Sales System API**

Sends valid payloads via HTTP POST to:

```
https://robocorp.com/inhuman-insurance-inc/sales-system-api
```

**4. Mark Work Item Status**

| Outcome             | Status    | Error Type    |
| ------------------- | --------- | ------------- |
| Successful API call | ✅ Done   | —             |
| Invalid payload     | ❌ Failed | `BUSINESS`    |
| API call failure    | ❌ Failed | `APPLICATION` |

---

## Work Item Payload Schema

Each work item contains a single `traffic_data` object:

```json
{
  "traffic_data": {
    "country": "FIN",
    "year": 2022,
    "rate": 3.2
  }
}
```

| Field     | Type      | Description                                            |
| --------- | --------- | ------------------------------------------------------ |
| `country` | `string`  | ISO 3166-1 alpha-3 country code (exactly 3 characters) |
| `year`    | `integer` | Year of the recorded statistic                         |
| `rate`    | `float`   | Road traffic fatality rate per 100,000 population      |

---

## Error Handling

The consumer task uses Robocorp's built-in error classification system:

**BUSINESS Error** — raised when input data is structurally invalid and cannot be retried:

- Country code is not exactly 3 characters
- Missing required fields in the payload

**APPLICATION Error** — raised when the external API fails unexpectedly:

- HTTP 4xx / 5xx responses from the sales system
- Network timeouts or connection errors

Work items marked as APPLICATION errors can be retried, while BUSINESS errors are considered terminal.

---

## API Reference

### External Sales System

**Endpoint:**

```
POST https://robocorp.com/inhuman-insurance-inc/sales-system-api
```

**Request Body:**

```json
{
  "country": "FIN",
  "year": 2022,
  "rate": 3.2
}
```

**Expected Responses:**

| Status   | Meaning                                     |
| -------- | ------------------------------------------- |
| `200 OK` | Record accepted successfully                |
| `4xx`    | Invalid request (triggers BUSINESS error)   |
| `5xx`    | Server failure (triggers APPLICATION error) |

---

## Key Functions

| Function                                     | Location   | Description                                                   |
| -------------------------------------------- | ---------- | ------------------------------------------------------------- |
| `produce_traffic_data()`                     | `tasks.py` | Entry point for the producer task                             |
| `load_traffic_data_as_table()`               | `tasks.py` | Downloads JSON and converts it to an RPA table                |
| `filter_and_sort_traffic_data(table)`        | `tasks.py` | Applies rate/gender filters and sorts by year descending      |
| `get_latest_data_by_country(table)`          | `tasks.py` | Deduplicates rows, keeping the most recent record per country |
| `create_work_item_payloads(table)`           | `tasks.py` | Transforms table rows into structured JSON payloads           |
| `save_work_item_payloads(payloads)`          | `tasks.py` | Saves each payload as an output work item                     |
| `process_traffic_data()`                     | `tasks.py` | Entry point for the consumer task                             |
| `post_traffic_data_to_sales_system(payload)` | `tasks.py` | Sends a payload to the external API and handles response      |

---

## Getting Started

### Prerequisites

- Python 3.8+
- [Robocorp RCC](https://github.com/robocorp/rcc) installed
- Internet access (for dataset download and API calls)

### Installation

**1. Clone the repository:**

```bash
git clone <repository-url>
cd <repository-folder>
```

**2. Install Python dependencies:**

```bash
pip install -r requirements.txt
```

### Running the Tasks

**Run the producer task first:**

```bash
rcc run -t produce_traffic_data
```

This downloads the dataset, processes it, and creates output work items.

**Then run the consumer task:**

```bash
rcc run -t process_traffic_data
```

This reads the work items, validates them, and sends data to the sales system API.

> **Note:** The producer must complete successfully before running the consumer. Work items are passed between them via Robocorp's work item queue.

---

## Future Improvements

- **Retry logic** — Automatically retry work items that fail with APPLICATION errors using exponential backoff
- **Extended validation** — Add ISO 3166-1 alpha-3 code verification, year range checks, and rate sanity bounds
- **Structured logging** — Integrate Python's `logging` module with log levels and file output for auditability
- **Configurable parameters** — Externalize the dataset URL, API endpoint, and filter thresholds into environment variables or a config file
- **Unit tests** — Add test coverage for filtering, deduplication, and payload validation logic
- **Monitoring dashboard** — Track work item throughput, failure rates, and error types via Robocorp Cloud analytics

---

## Author

**Siddhartha Thapa**

---

> Built with [Robocorp](https://robocorp.com/) · Data sourced from WHO Global Health Observatory
