import http.client
import json
import time

from urllib.parse import urlencode

from typing import Any, NotRequired, TypedDict


MIN_INTERVAL = 1 / 5
"""Airtable API rate limit of 5 requests per second"""

MARGIN = 0.05
"""50ms margin for each request, to ensure staying under limit"""

UPLOAD_BATCH_SIZE = 10
"""Airtable API upload limit of 10 records per HTTP (POST, PUT, PATCH) request"""


class RequestParams(TypedDict):
    fields: NotRequired[list[str]]
    offset: NotRequired[str]
    view: NotRequired[str]


class Record(TypedDict):
    id: str
    createdTime: NotRequired[str]
    fields: dict[str, Any]


class Table(object):
    def __init__(self, pat: str, app_id: str, table_id: str):
        """
        Create a client to interact with a table in an Airtable app (base).

        Args:
            - pat: your personal access token, e.g., "patID123.Value456"
            - app_id: the app's ID, e.g, "appABC123..."; the terms app and base are synonymous
            - table_id: either the table's ID or its Name, e.g, "tblABC123..." or "Table 1"
        """
        self._conn = http.client.HTTPSConnection("api.airtable.com")
        self._base_path = f"/v0/{app_id}/{table_id}"
        self._headers = {"Authorization": f"Bearer {pat}"}

        self._last_request: float = 0
        """time of the last request, as fractional seconds (time.monotonic)"""

    def __request(
        self,
        method: str,
        params: RequestParams | None = None,
        records: list[Record] | None = None,
    ) -> dict[str, Any]:
        """
        Maintains the actual mechanics of contacting the Airtable API: fetch, create,
        update, and delete funnel into here.

        Also keeps track of how often requests are made to stay under the Airtable API
        rate limit.
        """

        now = time.monotonic
        sleep = time.sleep

        if method not in ["GET", "PATCH"]:
            raise ValueError("__request only supports GET and PATCH")

        path = self._base_path
        headers = dict(self._headers)
        body = ""

        if params:
            kv_pairs = _flatten(params)
            path += "?" + urlencode(kv_pairs)

        if method == "PATCH":
            if not records:
                raise ValueError("PATCH but no records to update")
            headers["Content-Type"] = "application/json"
            body = json.dumps({"records": records})

        # delay this request if too soon
        elapsed = now() - self._last_request
        if elapsed < MIN_INTERVAL:
            delta = MIN_INTERVAL - elapsed
            sleep(delta + MARGIN)

        self._last_request = now()
        self._conn.request(method, path, body, headers)
        r = self._conn.getresponse()

        r_code = r.status
        r_data = json.loads(r.read())

        if r_code == 200:
            return r_data

        err_json = r_data.get("error", {})
        err_type = err_json.get("type", str(r_code))
        err_msg = err_json.get("message", json.dumps(r_data))

        raise Exception(f"{err_type}: {err_msg}")

    def fetch(self, fields: list[str] | None = None, view: str = "") -> list[Record]:
        """
        Fetch all records in table, or particular records by view.

        fields controls the fields returned by the API; the API omits "empty" fields.
        """
        params = RequestParams()
        if view:
            params["view"] = view
        if fields:
            params["fields"] = list(set(fields))

        all_records: list[Record] = []
        while True:
            result = self.__request("GET", params)
            all_records.extend(result["records"])

            params["offset"] = result.get("offset", "")  # get next page of results
            if not params["offset"]:
                break

        return all_records

    def patch(self, records: list[Record]) -> list[Record]:
        """Submits records for upsert and returns the updated records."""
        updated_records: list[Record] = []
        for chunk in _chunk(records, UPLOAD_BATCH_SIZE):
            result = self.__request("PATCH", records=chunk)
            updated_records.extend(result["records"])

        return updated_records


def _chunk(records: list[Record], n: int) -> list[list[Record]]:
    """
    Split records into a list of n-sized lists; the last list may have less than n records.
    """
    if n < 1:
        raise ValueError(f"{n} < 1")

    all_chunks: list[list[Record]] = []
    for i in range(0, len(records), n):
        all_chunks.append(records[i : i + n])

    return all_chunks


def _flatten(params: RequestParams) -> list[tuple[str, str]]:
    """Convert dict to list of string-pair tuples; handles special fields case."""
    pairs: list[tuple[str, str]] = []

    for x in params.get("fields", []):
        pairs.append(("fields[]", x))

    if x := params.get("offset"):
        pairs.append(("offset", x))

    if x := params.get("view"):
        pairs.append(("view", x))

    return pairs
