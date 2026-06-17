import os
import time


class BackendIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Optional demo sleep to make connection handling and least_conn effects visible.
        # Configure via the environment variable `DEMO_SLEEP_SECONDS` (float seconds).
        try:
            sleep_s = float(os.getenv('DEMO_SLEEP_SECONDS', '0'))
        except Exception:
            sleep_s = 0.0
        if sleep_s and sleep_s > 0:
            time.sleep(sleep_s)

        response['X-Backend-Server'] = os.getenv('BACKEND_ID', 'unknown')
        return response