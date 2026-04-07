import requests
from robocorp import workitems
from robocorp.tasks import task

@task
def process_traffic_data():
    """
    Consumer task for processing traffic data work items.

    Workflow:
    - Iterates through input work items
    - Validates payload structure
    - Sends valid data to external sales system API
    - Marks work item as done or failed based on response

    Failure handling:
    - BUSINESS error: Invalid input data
    - APPLICATION error: API call failure
    """
    # Iterate through all incoming work items
    for item in workitems.inputs:

        # Extract traffic data payload
        traffic_data = item.payload["traffic_data"]

        # Basic validation: country code should be exactly 3 characters (ISO format)
        if len(traffic_data["country"]) == 3:

            # Send data to external system
            status, return_json = post_traffic_data_to_sales_system(traffic_data)

            # Handle successful API response
            if status == 200:
                item.done()

            else:
                # Mark work item as failed due to application-level error
                item.fail(
                    exception_type="APPLICATION",
                    code="TRAFFIC_DATA_POST_FAILED",
                    message=return_json["message"],
                )
        else:
            # Mark work item as failed due to business validation error
            item.fail(
                exception_type="BUSINESS",
                code="INVALID_TRAFFIC_DATA",
                message=item.payload,
            )


def post_traffic_data_to_sales_system(traffic_data):
    """
    Sends traffic data to the external sales system API.

    Args:
        traffic_data (dict): Payload containing country, year, and rate

    Returns:
        tuple:
            - status_code (int): HTTP response status code
            - response_json (dict): Parsed JSON response
    """
    url = "https://robocorp.com/inhuman-insurance-inc/sales-system-api"

    # Perform POST request with JSON payload
    response = requests.post(url, json=traffic_data)

    # Return status and parsed response body
    return response.status_code, response.json()