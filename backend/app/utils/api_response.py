from flask import jsonify


def api_response(data=None, message="", success=True, status=200):
    """Single source of truth for the API response envelope.

    Shape matches the ApiResponse contract already used by SICO's Java
    microservices (mappale-http-utils), so this service stays consumable
    the same way if it is ever wired into sico-web directly.
    """
    body = {
        "message": message,
        "data": data,
        "success": success,
        "status": status,
    }
    return jsonify(body), status
