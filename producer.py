from robocorp import workitems
from robocorp.tasks import task
from RPA.HTTP import HTTP
from RPA.JSON import JSON
from RPA.Tables import Tables

# Initialize reusable library instances (shared across functions)
http = HTTP()
json = JSON()
table = Tables()

# File path for downloaded JSON data
TRAFFIC_JSON_FILE_PATH = "output/traffic.json"

# JSON data keys (used for consistent access and maintainability)
COUNTRY_KEY = "SpatialDim"
YEAR_KEY = "TimeDim"
RATE_KEY = "NumericValue"
GENDER_KEY = "Dim1"


@task
def produce_traffic_data():
    """
    Producer task for traffic data.

    Workflow:
    - Downloads raw JSON dataset
    - Converts JSON into structured table format
    - Applies filtering and sorting logic
    - Extracts latest data per country
    - Transforms data into payloads
    - Saves payloads as work items for downstream processing
    """
    # Download JSON dataset from remote source
    http.download(
        url="https://github.com/robocorp/inhuman-insurance-inc/raw/main/RS_198.json",
        target_file=TRAFFIC_JSON_FILE_PATH,
        overwrite=True,
    )

    # Load JSON into tabular structure
    traffic_data = load_traffic_data_as_table()

    # Apply filtering and sorting rules
    filtered_data = filter_and_sort_traffic_data(traffic_data)

    # Extract latest record per country
    filtered_data = get_latest_data_by_country(filtered_data)

    # Convert processed data into work item payloads
    payloads = create_work_item_payloads(filtered_data)

    # Persist payloads to output work items
    save_work_item_payloads(payloads)


def load_traffic_data_as_table():
    """
    Loads JSON data from file and converts it into a table structure.

    Returns:
        Table: Structured representation of JSON 'value' array
    """
    json_data = json.load_json_from_file(TRAFFIC_JSON_FILE_PATH)

    # Convert JSON array into RPA Table object
    return table.create_table(json_data["value"])


def filter_and_sort_traffic_data(data):
    """
    Filters and sorts traffic data based on business rules.

    Filtering criteria:
    - Rate must be below threshold
    - Gender must match 'both sexes'

    Sorting:
    - Sorted by year in descending order (latest first)

    Args:
        data (Table): Raw traffic data table

    Returns:
        Table: Filtered and sorted data
    """
    max_rate = 5.0
    both_genders = "BTSX"

    # Filter rows where rate is below threshold
    table.filter_table_by_column(data, RATE_KEY, "<", max_rate)

    # Filter rows for both genders only
    table.filter_table_by_column(data, GENDER_KEY, "==", both_genders)

    # Sort data by year descending (False = descending)
    table.sort_table_by_column(data, YEAR_KEY, False)

    return data


def get_latest_data_by_country(data):
    """
    Groups data by country and extracts the most recent record per country.

    Assumes data is pre-sorted by year in descending order.

    Args:
        data (Table): Filtered and sorted table

    Returns:
        list[dict]: Latest record for each country
    """
    # Group rows by country
    data = table.group_table_by_column(data, COUNTRY_KEY)

    latest_data_by_country = []

    # Iterate through each country group
    for group in data:
        # Extract the first row (latest due to prior sorting)
        first_row = table.pop_table_row(group)

        latest_data_by_country.append(first_row)

    return latest_data_by_country


def create_work_item_payloads(traffic_data):
    """
    Transforms processed data into structured payloads.

    Args:
        traffic_data (list[dict]): Latest country-level records

    Returns:
        list[dict]: Payloads formatted for work item creation
    """
    payloads = []

    for row in traffic_data:
        # Construct payload with required fields
        payload = dict(
            country=row[COUNTRY_KEY],
            year=row[YEAR_KEY],
            rate=row[RATE_KEY],
        )

        payloads.append(payload)

    return payloads


def save_work_item_payloads(payloads):
    """
    Saves payloads as output work items.

    Each payload is wrapped under 'traffic_data' key
    to standardize downstream consumption.

    Args:
        payloads (list[dict]): Data to be stored as work items
    """
    for payload in payloads:
        # Wrap payload in variables dictionary
        variables = dict(traffic_data=payload)

        # Create output work item
        workitems.outputs.create(variables)

