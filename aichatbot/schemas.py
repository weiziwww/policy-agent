POLICY_JSON_SCHEMA = {
  "type": "object",
  "required": ["kind", "action_types", "name", "description", "filter", "initialize", "check", "notify", "success", "fail"],
  "properties": {
    "kind": {"type": "string", "enum": ["platform", "constitution", "trigger"]},
    "action_types": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "name": {"type": "string", "minLength": 1},
    "description": {"type": "string"},
    "is_bundled": {"type": "boolean"},
    "filter": {"type": "string"},
    "initialize": {"type": "string"},
    "check": {"type": "string"},
    "notify": {"type": "string"},
    "success": {"type": "string"},
    "fail": {"type": "string"}
  },
  "additionalProperties": False
}