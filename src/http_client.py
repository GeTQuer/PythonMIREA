import base64
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.xml_api import decode, request_body


class ApiClient:
    def __init__(self, url, username="student", password="student"):
        self.url = url
        credentials = f"{username}:{password}".encode("utf-8")
        self.authorization = "Basic " + base64.b64encode(credentials).decode()

    def call(self, method, path, fields=None, xml=False):
        fields = fields or {}
        data = request_body(fields) if xml else None
        query = "" if xml or not fields else "?" + urlencode(fields)
        headers = {"Authorization": self.authorization,
                   "Content-Type": "application/xml"}
        request = Request(self.url + path + query, data=data,
                          headers=headers, method=method)
        with urlopen(request, timeout=10) as response:
            return decode(response.read())

    def api_submit_entity(self, **fields):
        return self.call("POST", "/api/submit/entity", fields, xml=True)[0]

    def api_fetch_entity(self, **fields):
        return self.call("GET", "/api/fetch/entity", fields)

    def api_update_entity(self, identifier, **fields):
        return self.call("POST", "/api/update/entity",
                         {"identifier": identifier, **fields})[0]

    def api_submit_command(self, entity, **fields):
        return self.call("POST", "/api/submit/command",
                         {"entity": entity, **fields}, xml=True)[0]

    def api_fetch_command(self, entity, **fields):
        return self.call("GET", f"/api/fetch/command/{entity}", fields)

    def api_update_command(self, identifier, **fields):
        return self.call("POST", "/api/update/command",
                         {"identifier": identifier, **fields})[0]

    def api_fetch_result(self, command, **fields):
        return self.call("GET", f"/api/fetch/result/{command}", fields)

    def api_fetch_report(self):
        return self.call("GET", "/api/fetch/report")
