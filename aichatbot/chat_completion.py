from openai import OpenAI
import logging
import re


logger = logging.getLogger(__name__)

class ChatCompletion:

    def __init__(self):
        self.llm_client = OpenAI(api_key="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")

    def chat_completion(self, system_prompt, user_prompt, type="json_object", n=1):
        kwargs = {
            "model": "gpt-5.1",
            "response_format": {"type": type},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if isinstance(n, int) and n > 1:
            kwargs["n"] = n

        response = self.llm_client.chat.completions.create(**kwargs)

        if isinstance(n, int) and n > 1:
            # collect all completions
            return [choice.message.content for choice in response.choices]

        # original behavior
        return response.choices[0].message.content

    def text_embedding(self, text):
        retries = 0
        while retries < 3:
            try:
                response = self.llm_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text
                )
                return response.data[0].embedding
            except Exception as e:
                retries += 1
                logger.error(f"Error in text_embedding: {text}, {e}")

    def __batch_text_embedding(self, texts):
        retries = 0
        while retries < 3:
            try:
                response = self.llm_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts
                )
                return [item.embedding for item in response.data]
            except Exception as e:
                retries += 1
                logger.error(f"Error in batch_text_embedding: {e}")
        return [None] * len(texts)
    
    def list_text_embedding(self, texts, batch_size=50):
        if len(texts) <= batch_size:
            return self.__batch_text_embedding(texts)
        
        batches = [texts[i:i+batch_size] for i in range(0, len(texts), batch_size)]
        results = []
        
        for i, batch in enumerate(batches):
            try:
                batch_result = self.__batch_text_embedding(batch)
                results.extend(batch_result)
            except Exception as e:
                logger.error(f"Error processing batch {i}: {e}")
                results.extend([None] * len(batch))
        
        return results

    def extract_xml(self, xml_str, tag):
        pattern = re.compile(fr"<{tag}>(.*?)</{tag}>", re.DOTALL)
        result = pattern.findall(xml_str)
        if not result:
            return None
        elif len(result) == 1:
            return result[0]
        else:
            return [match.strip() for match in result]