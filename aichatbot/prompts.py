import logging
import re
import json

from chat_completion import ChatCompletion


logger = logging.getLogger(__name__)


class PolicyLLMBuddy:

    def __init__(self):
        self.llm_client = ChatCompletion()
        self.debug = True

    def refine_policy_with_conversation(self, name, user_message, current_draft=None):
      current_draft_str = current_draft if current_draft is not None else ""

      system_prompt = """
          <Role>
              You are an expert in online community governance and voting workflows.
              Your job is to help the user turn a vague or informal policy idea
              into a precise, implementation friendly natural language policy.
          </Role>

          <Goals>
              1. Understand the user's intent behind the policy.
              2. Identify missing details that would matter for implementation
                  such as who can propose, who can vote, time windows,
                  thresholds, veto powers, and scope of actions.
              3. Propose a refined policy draft in clear, concise natural language.
              4. Ask a small number of targeted questions to further clarify
                  any remaining ambiguity.
          </Goals>

          <Guidelines>
              <ConversationStyle>
                  Speak to the user in plain language and keep answers concise.
                  Do not overwhelm the user with too many questions at once.
                  Prefer at most three clarifying questions per turn.
              </ConversationStyle>

              <PolicyPrecision>
                  Make the policy text concrete enough that an engineer could
                  later translate it into code.
                  Whenever needed, introduce reasonable defaults but clearly label
                  them as assumptions so the user can correct them.
              </PolicyPrecision>
          </Guidelines>

          You must always respond in the following XML format

          <AssistantMessage>
              A friendly explanation of how you understood the user's intent
              and what you changed or clarified in this turn.
          </AssistantMessage>

          <ClarifyingQuestions>
              A numbered list of specific questions for the user to answer
              in the next message. If nothing is unclear, you may write
              "None" instead.
          </ClarifyingQuestions>

          <RewrittenPolicy>
              The current best version of the policy in precise natural language.
              This should be a standalone description of the rule that the user
              can edit or accept.
          </RewrittenPolicy>
      """

      user_prompt = f"""
          <Name>{name}</Name>
          <UserMessage>{user_message}</UserMessage>
          <CurrentDraft>{current_draft_str}</CurrentDraft>
      """

      response = self.llm_client.chat_completion(
          system_prompt=system_prompt,
          user_prompt=user_prompt,
          type="text",
      )

      assistant_message = self.llm_client.extract_xml(response, "AssistantMessage")
      clarifying_questions = self.llm_client.extract_xml(response, "ClarifyingQuestions")
      rewritten_policy = self.llm_client.extract_xml(response, "RewrittenPolicy")

      return {
          "assistant_message": assistant_message,
          "clarifying_questions": clarifying_questions,
          "rewritten_policy": rewritten_policy,
      }


    def generate_policy_procedure(self, name, description, example=None):
        system_prompt = """
            <Tasks>
                You are an expert in online community governance and voting workflows.
                A user will describe, often vaguely, how they want a voting rule or decision
                procedure to work for a given policy.

                You are given
                    - a human readable name for the policy
                    - a short natural language description or draft
                    - a JSON representation of the policy and related procedures or modules
                      which you should treat as the source of truth for available fields
                      and structure

                Your job is to
                    1) resolve any vagueness in the description by adding explicit assumptions
                    2) extract all key parameters needed for implementation
                    3) decompose the rule into a clear step by step voting procedure
                       in natural language that can later be translated into code
            </Tasks>

            <Guidelines>
                <ClarifyScope>
                    Explicitly answer
                        - Who is allowed to propose
                        - What actions or decisions this rule applies to
                        - Who is allowed to vote
                </ClarifyScope>

                <Parameters>
                    Identify concrete values or defaults for
                        - voting window length
                        - passing conditions such as majority thresholds
                        - failure conditions such as no quorum or tie
                        - special roles such as veto or tie breaker
                </Parameters>

                <Example>
                    Write the procedure as a numbered list of steps that a backend system
                    could implement For example
                        1 When a proposal is created
                        2 Notify eligible voters
                        3 Open voting for the configured window
                        4 While voting is open count and update tallies in a specific way
                        5 At the end of the window apply pass and fail logic
                        6 Trigger follow up actions based on the result
                </Example>

                <AmbiguityHandling>
                    If the user description or JSON is ambiguous or incomplete
                    you MUST choose reasonable defaults and state them explicitly
                    under Assumptions
                    Do not ask follow up questions
                    Always produce a complete procedure that could be implemented
                    by an engineer
                </AmbiguityHandling>

                <Style>
                    The procedure should be concrete and implementation friendly
                    yet still written in plain natural language
                    Each step should describe
                        - when the step is triggered
                        - what conditions are checked
                        - what state changes or actions occur
                </Style>
            </Guidelines>

            You must write your output in the following XML format

            <Assumptions>
                Your explicit assumptions and resolved ambiguities
                written as a short list in natural language
            </Assumptions>

            <Procedure>
                A numbered list of steps in natural language describing
                the voting workflow from start to finish
                Each step should start with a number followed by a period
                for example
                <Example>
                  1 When a proposal is created
                  2 Notify all eligible voters
                <Example>
            </Procedure>
        """

        user_prompt = f"""
            <Name>{name}</Name>
            <Description>{description}</Description>
        """

        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            type="text",
        )

        procedure = self.llm_client.extract_xml(response, "Procedure")
        assumptions = self.llm_client.extract_xml(response, "Assumptions")

        if self.debug:
            logger.info("Generated policy procedure for %s", name)

        return {
            "assumptions": assumptions,
            "procedure": procedure,
        }
    
    def summarize_model_context(self, raw_model_code):
        system_prompt = """
          You are a Senior Python Developer. Your task is to read the provided Python source code (model definitions) 
          and create a concise "API Reference" for another AI developer.
          
          Focus strictly on the functions of following classes:
          - Proposal
          - Vote
          - CommunityUser (or User)
          - Community
          
          For each class, list:
          1. Key fields/attributes available (especially relations like vote_set).
          2. Every helper methods (e.g., get_yes_votes() for proposal class), and give a brief description on how to use it.
          
          Output format: Plain text, structured as a developer documentation.
        """
        
        user_prompt = f"""
        Here is the content of `models.py`:
        
        {raw_model_code}
        
        Please summarize the API context.
        """

        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            type="text"
        )
        
        if self.debug:
            logger.info("Generated API Context Summary")
            
        return response

    def generate_code_with_context(self, user_description, api_context):
        system_prompt = f"""
        <Role>
            You are a PolicyKit Algorithm Developer. 
            You must write the `check` function for a governance policy.
        </Role>

        <API_Context>
            You MUST use the definitions found in this API Reference:
            {api_context}
            
            Global variables available in scope:
            - proposal (Proposal object)
            - action (The action object)
            - users (List of community users)
            - datetime (module)
        </API_Context>

        <Goal>
            Write python code to determine if the proposal passes using the helper methods of each class.
            e.g. 
            <Sample Code>
              yes_votes = proposal.get_yes_votes().count()
              no_votes = proposal.get_no_votes().count()
              proposal.data.set("yes_votes_num", yes_votes)
              proposal.data.set("no_votes_num", no_votes)
              if yes_votes >= variables.minimum_yes_required:
                  slack.post_message(
                      post_type="channel",
                      channel=proposal.data.get("vote_channel"),
                  )
                  return PASSED
              elif no_votes >= variables.maximum_no_allowed:
                  slack.post_message(
                      post_type="channel",
                      channel=proposal.data.get("vote_channel"),
                  )
                  return FAILED

              return PROPOSED
            </Sample Code>
            Return: PASSED, FAILED, or PROPOSED.
            
            IMPORTANT: Do NOT hallucinate methods. Only use attributes/methods found in the API_Context.
        </Goal>
        
        <Rules>
            1. No markdown formatting (no ```python).
            2. Concise logic.
            3. Use English comments.
        </Rules>
        """

        user_prompt = f"""
        User Requirement: "{user_description}"
        
        Write the Python code.
        """

        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            type="text"
        )
        
        return self._extract_clean_code(response)

    def verify_and_fix_code(self, generated_code, user_description, api_context):
        
        """
        Feeds the code back to the AI to check against the API context and User Requirement.
        """
        system_prompt = f"""
        You are a Code Reviewer and QA Engineer for PolicyKit.
        
        <Input Data>
        1. User Requirement: "{user_description}"
        2. Available API Context:
        {api_context}
        </Input Data>
        
        <Task>
        Review the provided Python code.
        1. Does it satisfy the User Requirement?
        2. Does it ONLY use methods/attributes existent in the API Context? (Check for hallucinated function names).
        3. Is the logic sound?
        
        If the code is correct, output it exactly as is.
        If there are errors (logic or API misuse), FIX the code and output ONLY the fixed code.
        
        Output Format: Pure Python code string. No markdown, no explanations.
        """

        user_prompt = f"""
        Code to Review:
        {generated_code}
        """

        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            type="text"
        )

        return self._extract_clean_code(response)
    def _extract_clean_code(self, text):
        pattern = r"```python\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        return text.replace("```", "").strip()