import json
import os
from prompts import PolicyLLMBuddy


def test_refine_policy():
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

def test_full_workflow_with_context():
    buddy = PolicyLLMBuddy()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # model_file_path = os.path.join(current_dir, "..", "models.py")
    
    # model_file_path = os.path.abspath(model_file_path) 

    summary_file_path = os.path.join(current_dir, "model_summary1.txt")

    api_context_summary = ""

    if os.path.exists(summary_file_path):
        with open(summary_file_path, "r", encoding="utf-8") as f:
            api_context_summary = f.read()
    else:
        model_file_path = os.path.join(current_dir, "..", "models.py")
        model_file_path = os.path.abspath(model_file_path) 
        
        with open(model_file_path, "r", encoding="utf-8") as f:
            raw_model_code = f.read()
        
        print(f"Loaded models.py")

        api_context_summary = buddy.summarize_model_context(raw_model_code)
        
        with open(summary_file_path, "w", encoding="utf-8") as f:
            f.write(api_context_summary)
        print(f"Saved new API summary to {summary_file_path}")

    # api_context_summary = buddy.summarize_model_context(raw_model_code)
    # print("-" * 20 + " API Summary " + "-" * 20)
    # print(api_context_summary)
    # print("-" * 50)

    # user_requirement1 = "If user 'king' proposes, pass immediately. Otherwise 'king' must vote YES."
    
    # user_requirement2 = "If majority users vote for yes, then pass"

    # user_requirement = user_requirement2
        
    test_cases_path = os.path.join(current_dir, "policy_test_cases.json")
    with open(test_cases_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)


    for index, case in enumerate(test_cases, 1):
        print(f"\n [Test Case {index}/{len(test_cases)}]: {case['name']}")

        print("   >> Generating Draft Code...")
        initial_code = buddy.generate_code_with_context(case['description'], api_context_summary)
        
        print("   >> Verifying and Fixing...")
        final_code = buddy.verify_and_fix_code(initial_code, case['description'], api_context_summary)
        
        print("   " + "-" * 30)
        print(final_code)
        print("   " + "-" * 30)

    # initial_code = buddy.generate_code_with_context(user_requirement, api_context_summary)
    
    # print("--- Initial Draft Code ---")
    # print(initial_code)
    # print("--------------------------")

    # final_code = buddy.verify_and_fix_code(initial_code, user_requirement, api_context_summary)
    
    # print("--- Final Verified Code ---")
    # print(final_code)
    # print("---------------------------")

if __name__ == "__main__":
    # print("Testing refine_policy_with_conversation")
    # test_refine_policy()
    # print()
    # print("Testing generate_policy_procedure")
    # test_generate_procedure()
    # print()
    test_full_workflow_with_context()
