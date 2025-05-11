import json
import datetime

def getValidRules():
    with open('data/rules.json', 'r') as file:
        rules = json.load(file)
    
    valid_rules = []
    current_time = datetime.datetime.now(datetime.timezone.utc)
    for rule in rules:
        if 'fields' in rule:
            fields = rule['fields']
            if 'start' in fields and 'end' in fields:
                start = datetime.datetime.fromisoformat(fields['start'].replace('Z', '+00:00'))
                end = datetime.datetime.fromisoformat(fields['end'].replace('Z', '+00:00'))
                if start <= current_time <= end:
                    valid_rules.append({
                        "id": rule.get("id", ""),
                        "createdTime": rule.get("createdTime", ""),
                        "fields": {
                            "ruleNumber": fields.get("ruleNumber", ""),
                            "start": fields.get("start", ""),
                            "end": fields.get("end", ""),
                            "disableWeathery": fields.get("disableWeathery", False),
                            "comment": fields.get("comment", "")
                        }
                    })
    
    return valid_rules

