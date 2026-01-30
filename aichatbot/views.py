class GenerateFromText(APIView):
    def post(self, request):
        client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", None))
        resp = client.responses.create(
            model="gpt-5",
            input=messages,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "policy_schema",
                    "schema": POLICY_JSON_SCHEMA,
                    "strict": True
                }
            }
        )