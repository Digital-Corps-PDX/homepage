import http.client
import json
import time

from urllib.parse import urlencode

from typing import Any, NotRequired, TypedDict


MIN_REQ_INTERVAL = 1 / 5  # The Airtable API limits the rate for any request to "5 requests per second per base"
UPLOAD_BATCH_SIZE = 10  # The Airtable API limits uploads (POST, PATCH) per request to 10 records per HTTP request


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

        # Record time of the last request, stay under rate limit
        self._last_request: float = 0

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

        # Space this request out from a previous request
        elapsed = time.monotonic() - self._last_request
        if elapsed < MIN_REQ_INTERVAL:
            sleep = MIN_REQ_INTERVAL - elapsed  # + (5 / 100)  # +.05s to make sure we've waited long enough
            time.sleep(sleep)

        self._last_request = time.monotonic()
        self._conn.request(method, path, body, headers)
        r = self._conn.getresponse()

        r_code = r.status
        r_data = json.loads(r.read())

        # All's good!
        if r_code == 200:
            return r_data

        error_json = r_data.get("error", {})

        raise Exception(
            f"type: {error_json.get('type', str(r_code))}: {error_json.get('message', json.dumps(r_data))}",
        )

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
