"""Uniform error envelope so the frontend can render one message shape."""
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    detail = None
    errors = None

    if isinstance(data, dict):
        if "detail" in data and len(data) == 1:
            detail = str(data["detail"])
        else:
            errors = data
            first_key = next(iter(data), None)
            first_value = data.get(first_key)
            if isinstance(first_value, (list, tuple)) and first_value:
                first_value = first_value[0]
            detail = str(first_value) if first_value is not None else "Request failed."
    elif isinstance(data, (list, tuple)) and data:
        errors = {"non_field_errors": list(data)}
        detail = str(data[0])
    else:
        detail = str(data)

    payload = {"detail": detail}
    if errors:
        payload["errors"] = errors
    response.data = payload
    return response
