from prompts import PolicyLLMBuddy


def procedure_sequence_generation():
    buddy = PolicyLLMBuddy()

    name = "Channel rename policy"
    user_message = "When someone wants to change the channel name, admins should somehow agree on it"
    current_draft = None

    result = buddy.refine_policy_with_conversation(
        name=name,
        user_message=user_message,
        current_draft=current_draft,
    )

    print("AssistantMessage")
    print(result["assistant_message"])
    print()
    print("ClarifyingQuestions")
    print(result["clarifying_questions"])
    print()
    print("RewrittenPolicy")
    print(result["rewritten_policy"])
    print("-" * 80)


def test_generate_procedure():
    buddy = PolicyLLMBuddy()

    name = "Channel rename policy"
    description = "Admins vote on whether a proposed new channel name should be accepted"
    policy_json = {}

    result = buddy.generate_policy_procedure(
        name=name,
        description=description
    )

    print("Assumptions")
    print(result["assumptions"])
    print()
    print("Procedure")
    print(result["procedure"])
    print("-" * 80)


if __name__ == "__main__":
    print("Testing refine_policy_with_conversation")
    test_refine_policy()
    print()
    print("Testing generate_policy_procedure")
    test_generate_procedure()