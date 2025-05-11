import airtable


class Airtabler:
    def __init__(self, base_id, api_key):
        self.base_id = base_id
        self.api_key = api_key
        self.airtable = airtable.Airtable(base_id, api_key)

    def getAllData(self, table_name):
        records = []
        offset = None

        while True:
            response = self.airtable.get(table_name, offset=offset)
            records.extend(response.get('records', []))
            offset = response.get('offset')
            if not offset:
                break

        return records