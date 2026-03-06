import sys
import datetime
import inspect
import re
import random
from types import ModuleType
from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional


mock_pe = ModuleType("policyengine")
mock_pe.PASSED = "passed"
mock_pe.FAILED = "failed"
mock_pe.PROPOSED = "proposed"
sys.modules["policyengine"] = mock_pe

mock_pe_models = ModuleType("policyengine.models")
sys.modules["policyengine.models"] = mock_pe_models

class MockQuerySet:
    def __init__(self, items: List[Any]): self._items = items
    def count(self): return len(self._items)
    def exists(self): return len(self._items) > 0
    def first(self): return self._items[0] if self._items else None
    def all(self): return self
    def order_by(self, key):
        if not self._items: return self
        reverse = key.startswith("-")
        key = key[1:] if reverse else key
        sorted_items = sorted(self._items, key=lambda x: getattr(x, key, 0), reverse=reverse)
        return MockQuerySet(sorted_items)
    def filter(self, **kwargs):
        filtered = self._items
        for key, value in kwargs.items():
            if "__in" in key:
                field_name = key.split("__")[0]
                filtered = [i for i in filtered if getattr(i, field_name) in value]
            else:
                filtered = [i for i in filtered if getattr(i, key) == value]
        return MockQuerySet(filtered)
    def __iter__(self): return iter(self._items)
    def __len__(self): return len(self._items)

class MockDataStore:
    def __init__(self): self.data = {} 
    def set(self, key, value): self.data[key] = value
    def get(self, key, default=None): return self.data.get(key, default)
    def save(self): pass 
    def __getitem__(self, key): return self.data[key]
    def __setitem__(self, key, value): self.data[key] = value

@dataclass
class MockUser:
    username: str
    id: int = None
    roles: List[str] = field(default_factory=list)
    def has_role(self, role_name): return role_name in self.roles
    def __hash__(self): return hash(self.username)

@dataclass
class MockVote:
    user: MockUser
    boolean_value: Optional[bool] = None
    value: Optional[str] = None 
    vote_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    @property
    def user_id(self): return self.user.id

@dataclass
class MockAction:
    initiator: MockUser

class MockProposal:
    PROPOSED = "proposed"
    PASSED = "passed"
    FAILED = "failed"
    def __init__(self, action: MockAction, created_at: datetime.datetime = None):
        self.action = action
        self.status = self.PROPOSED
        self.data = MockDataStore()
        self.votes: List[MockVote] = []
        self.proposal_time = created_at or datetime.datetime.now()
    def get_yes_votes(self, users=None):
        votes = [v for v in self.votes if v.boolean_value is True]
        if users: votes = [v for v in votes if v.user in users]
        return MockQuerySet(votes)
    def get_no_votes(self, users=None):
        votes = [v for v in self.votes if v.boolean_value is False]
        if users: votes = [v for v in votes if v.user in users]
        return MockQuerySet(votes)
    def get_all_boolean_votes(self, users=None):
        votes = [v for v in self.votes if v.boolean_value is not None]
        if users: votes = [v for v in votes if v.user in users]
        return MockQuerySet(votes)
    def get_choice_votes(self, value=None):
        votes = [v for v in self.votes if v.value == value] if value else [v for v in self.votes if v.value is not None]
        return MockQuerySet(votes)
    def get_time_elapsed(self):
        return datetime.datetime.now() - self.proposal_time
    def _pass_evaluation(self): self.status = self.PASSED
    def _fail_evaluation(self): self.status = self.FAILED

sys.modules["policyengine.models"].Proposal = MockProposal

# ==========================================
# 2. The Sandbox Executor
# ==========================================
def run_policy_check(code_str: str, proposal: MockProposal, users: List[MockUser]):
    context = {
        'proposal': proposal, 'action': proposal.action, 'users': users,
        'datetime': datetime, 'Proposal': MockProposal,
        'PASSED': "passed", 'FAILED': "failed", 'PROPOSED': "proposed"
    }
    try: exec(code_str, context)
    except Exception as e: return f"CRASH (Syntax/Import): {e}"

    if 'check' not in context: return "ERROR: No 'check' function defined in code."
    
    check_func = context['check']
    sig = inspect.signature(check_func)
    args = {}
    
    for param in sig.parameters:
        if param in context:
            args[param] = context[param]
        elif param == 'variables':
            class MockVariables: pass
            mock_vars = MockVariables()
            mock_vars.proposal = proposal
            if "winning_option" in code_str: mock_vars.winning_option = "Option A"
            args[param] = mock_vars
            
    try: return check_func(**args)
    except Exception as e: return f"CRASH (Runtime): {e}"

# ==========================================
# 3. GENERATIVE TEST BUILDER
# ==========================================
def parse_output_file(file_path):
    try:
        with open(file_path, 'r') as f: content = f.read()
    except FileNotFoundError: return []
    pattern = r"\[Test Case \d+/\d+\]:\s*(.*?)\n.*?[-]{30,}\n(.*?)\n\s*[-]{30,}"
    return [(n.strip(), c.strip()) for n, c in re.findall(pattern, content, re.DOTALL)]

def build_test_suite(test_name):
    """
    Procedurally generates tests with RANDOM numbers of users and votes.
    Returns: proposal, users, expected_result, details_string
    """
    suites = []
    
    def generate_random_users(num_users, roles=None):
        users = []
        for i in range(num_users):
            role = [random.choice(roles)] if roles else []
            users.append(MockUser(username=f"user_{i}", id=i, roles=role))
        return users

    # --------------------------------------------------------------------
    if "Simple Majority" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(3, 30)
                users = generate_random_users(t_users)
                p = MockProposal(MockAction(initiator=users[0]))
                
                y_votes = random.randint(0, t_users)
                n_votes = t_users - y_votes
                for u in users[:y_votes]: p.votes.append(MockVote(user=u, boolean_value=True))
                for u in users[y_votes:]: p.votes.append(MockVote(user=u, boolean_value=False))
                
                if t_users == 0: exp = "proposed"
                elif y_votes > t_users / 2: exp = "passed"
                else: exp = "failed"
                
                detail = f"[Total: {t_users:02}] {y_votes:02} YES | {n_votes:02} NO"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Unanimous Consensus" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(2, 20)
                users = generate_random_users(t_users)
                p = MockProposal(MockAction(initiator=users[0]))
                
                is_unanimous = random.choice([True, False])
                y_votes = t_users if is_unanimous else random.randint(0, t_users - 1)
                n_votes = t_users - y_votes
                
                for u in users[:y_votes]: p.votes.append(MockVote(user=u, boolean_value=True))
                for u in users[y_votes:]: p.votes.append(MockVote(user=u, boolean_value=False))
                
                if n_votes > 0: exp = "failed"
                elif t_users > 0 and y_votes == t_users: exp = "passed"
                else: exp = "proposed"
                
                detail = f"[Total: {t_users:02}] {y_votes:02} YES | {n_votes:02} NO"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Benevolent Dictator" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(3, 10)
                users = generate_random_users(t_users)
                king = MockUser(username="king_arthur", id=999)
                users.append(king)
                
                king_initiates = random.choice([True, False])
                p = MockProposal(MockAction(initiator=king if king_initiates else users[0]))
                
                king_vote = "N/A"
                if king_initiates:
                    exp = "passed"
                else:
                    vote_choice = random.choice([True, False, None])
                    if vote_choice is not None:
                        p.votes.append(MockVote(user=king, boolean_value=vote_choice))
                        king_vote = "YES" if vote_choice else "NO"
                    else:
                        king_vote = "Did not vote"
                        
                    if vote_choice is True: exp = "passed"
                    elif vote_choice is False: exp = "failed"
                    else: exp = "proposed"
                    
                detail = f"King Initiates: {str(king_initiates):<5} | King Vote: {king_vote}"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Board Approval" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(5, 15)
                users = generate_random_users(t_users, roles=["Board Member", "Member"])
                users[0].roles = ["Board Member"] # Force at least one board member
                
                p = MockProposal(MockAction(initiator=users[0]))
                b_yes, b_no, reg_votes = 0, 0, 0
                
                for u in users:
                    voted = random.choice([True, False])
                    if voted:
                        val = random.choice([True, False])
                        p.votes.append(MockVote(user=u, boolean_value=val))
                        if u.has_role("Board Member"):
                            if val: b_yes += 1
                            else: b_no += 1
                        else: reg_votes += 1
                            
                if (b_yes + b_no) == 0: exp = "proposed"
                elif b_yes > b_no: exp = "passed"
                elif b_no > b_yes: exp = "failed"
                else: exp = "proposed"
                
                detail = f"Board: {b_yes} YES, {b_no} NO | Regular User Votes: {reg_votes}"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Jury Duty" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(5, 10)
                users = generate_random_users(t_users)
                p = MockProposal(MockAction(initiator=users[0]))
                
                jurors = random.sample(users, 3)
                p.data.data["jury_user_ids"] = [j.id for j in jurors]
                
                num_voted = random.randint(0, 3)
                j_yes, j_no = 0, 0
                for j in range(num_voted):
                    val = random.choice([True, False])
                    p.votes.append(MockVote(user=jurors[j], boolean_value=val))
                    if val: j_yes += 1
                    else: j_no += 1
                    
                if num_voted >= 3:
                    if j_yes >= 2: exp = "passed"
                    else: exp = "failed"
                else:
                    exp = "proposed"
                    
                detail = f"Jurors Selected: 3 | Jurors Voted: {num_voted} | Jury YES: {j_yes}, Jury NO: {j_no}"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Token Weighted" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(3, 10)
                users = generate_random_users(t_users)
                p = MockProposal(MockAction(initiator=users[0]))
                
                balances = {}
                yes_tokens = 0
                total_tokens = 0
                
                for u in users:
                    bal = random.randint(1, 100)
                    balances[u.id] = bal
                    balances[str(u.id)] = bal 
                    
                    voted = random.choice([True, False, None])
                    if voted is not None:
                        p.votes.append(MockVote(user=u, boolean_value=voted))
                        total_tokens += bal
                        if voted: yes_tokens += bal
                
                p.data.data["token_balances"] = balances
                
                if total_tokens == 0: exp = "proposed"
                elif yes_tokens > 0.6 * total_tokens: exp = "passed"
                else: exp = "proposed"
                
                detail = f"YES Tokens: {yes_tokens:03d} | Total Voted Tokens: {total_tokens:03d}"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Lazy Consensus" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(3, 10)
                users = generate_random_users(t_users)
                
                hours_old = random.choice([10, 50])
                p = MockProposal(MockAction(initiator=users[0]), 
                                 created_at=datetime.datetime.now() - datetime.timedelta(hours=hours_old))
                
                y_votes, n_votes = 0, 0
                for u in users:
                    voted = random.choice([True, False, None])
                    if voted is not None:
                        p.votes.append(MockVote(user=u, boolean_value=voted))
                        if voted: y_votes += 1
                        else: n_votes += 1
                
                if hours_old >= 48 and n_votes == 0: exp = "passed"
                elif n_votes > 0:
                    if y_votes > n_votes: exp = "passed"
                    else: exp = "failed"
                else: exp = "proposed"
                
                detail = f"Age: {hours_old}h | {y_votes} YES | {n_votes} NO"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Majority with Timeout" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(3, 10)
                users = generate_random_users(t_users)
                
                days_old = random.choice([1, 4])
                p = MockProposal(MockAction(initiator=users[0]), 
                                 created_at=datetime.datetime.now() - datetime.timedelta(days=days_old))
                
                y_votes, n_votes = 0, 0
                for u in users:
                    voted = random.choice([True, False, None])
                    if voted is not None:
                        p.votes.append(MockVote(user=u, boolean_value=voted))
                        if voted: y_votes += 1
                        else: n_votes += 1
                        
                if y_votes > n_votes: exp = "passed"
                elif days_old >= 3: exp = "failed"
                else: exp = "proposed"
                
                detail = f"Age: {days_old}d | {y_votes} YES | {n_votes} NO"
                return p, users, exp, detail
            suites.append({"setup": setup})

    # --------------------------------------------------------------------
    elif "Ranked Choice" in test_name:
        for i in range(3):
            def setup():
                t_users = random.randint(5, 15)
                users = generate_random_users(t_users)
                p = MockProposal(MockAction(initiator=users[0]))
                
                winning_option = "Option A"
                win_votes, tot_votes = 0, 0
                
                for u in users:
                    voted = random.choice([True, False])
                    if voted:
                        choice = random.choice(["Option A", "Option B", "Option C"])
                        p.votes.append(MockVote(user=u, value=choice))
                        tot_votes += 1
                        if choice == winning_option:
                            win_votes += 1
                            
                if tot_votes == 0: exp = "proposed"
                elif win_votes > tot_votes / 2: exp = "passed"
                else: exp = "failed"
                
                detail = f"Total Votes Cast: {tot_votes:02} | Votes for Winning Option: {win_votes:02}"
                return p, users, exp, detail
            suites.append({"setup": setup})

    return suites

# ==========================================
# 4. Main Execution
# ==========================================
if __name__ == "__main__":
    output_file = "output.txt"
    extracted_cases = parse_output_file(output_file) 
    
    if not extracted_cases:
        print("No test cases found. Ensure output.txt exists and is formatted correctly.")
        sys.exit()

    print(f"==================================================")
    print(f" PolicyKit Generative Sandbox Test Runner")
    print(f"==================================================\n")

    total_tests = 0
    passed_tests = 0

    for test_name, code_snippet in extracted_cases:
        print(f"Running Policy: {test_name}")
        
        suite = build_test_suite(test_name)
        
        for scenario in suite:
            total_tests += 1
            # Execute the setup function to get the randomized state + details
            proposal, users, expected, detail_string = scenario["setup"]()
            
            # Feed the generated code and the randomized payload into the checker
            actual_result = run_policy_check(code_snippet, proposal, users)
            
            # Formatted Output
            if actual_result == expected:
                passed_tests += 1
                print(f"  [PASS] Evaluated as '{expected:<8}' <- Context: {detail_string}")
            else:
                print(f"  [FAIL] Context: {detail_string}")
                print(f"         Expected: '{expected}', Got: '{actual_result}'")
                
        print("-" * 65)

    print(f"\n==================================================")
    print(f" TEST SUMMARY: {passed_tests} / {total_tests} scenarios passed.")
    print(f"==================================================")

# import sys
# import datetime
# import inspect
# import re
# from types import ModuleType
# from dataclasses import dataclass, field
# from typing import List, Any, Dict, Optional

# # ==========================================
# # 0. PRE-FLIGHT: Mock Missing Modules
# # ==========================================
# mock_pe = ModuleType("policyengine")
# mock_pe.PASSED = "passed"
# mock_pe.FAILED = "failed"
# mock_pe.PROPOSED = "proposed"
# sys.modules["policyengine"] = mock_pe

# mock_pe_models = ModuleType("policyengine.models")
# sys.modules["policyengine.models"] = mock_pe_models

# # ==========================================
# # 1. Mocking the Django/PolicyKit Data Layer
# # ==========================================

# class MockQuerySet:
#     def __init__(self, items: List[Any]):
#         self._items = items

#     def count(self):
#         return len(self._items)

#     def exists(self):
#         return len(self._items) > 0

#     def first(self):
#         return self._items[0] if self._items else None

#     def all(self):
#         return self

#     def order_by(self, key):
#         if not self._items:
#             return self
#         reverse = False
#         if key.startswith("-"):
#             key = key[1:]
#             reverse = True
#         sorted_items = sorted(
#             self._items, 
#             key=lambda x: getattr(x, key, 0), 
#             reverse=reverse
#         )
#         return MockQuerySet(sorted_items)

#     def filter(self, **kwargs):
#         filtered = self._items
#         for key, value in kwargs.items():
#             if "__in" in key:
#                 field_name = key.split("__")[0]
#                 filtered = [i for i in filtered if getattr(i, field_name) in value]
#             else:
#                 filtered = [i for i in filtered if getattr(i, key) == value]
#         return MockQuerySet(filtered)

#     def __iter__(self):
#         return iter(self._items)

#     def __len__(self):
#         return len(self._items)

# class MockDataStore:
#     def __init__(self):
#         self.data = {} 

#     def set(self, key, value):
#         self.data[key] = value

#     def get(self, key, default=None):
#         return self.data.get(key, default)

#     def save(self):
#         pass 

#     def __getitem__(self, key):
#         return self.data[key]

#     def __setitem__(self, key, value):
#         self.data[key] = value

# @dataclass
# class MockUser:
#     username: str
#     id: int = None
#     roles: List[str] = field(default_factory=list)

#     def has_role(self, role_name):
#         return role_name in self.roles
    
#     def __hash__(self):
#         return hash(self.username)

# @dataclass
# class MockVote:
#     user: MockUser
#     boolean_value: Optional[bool] = None
#     value: Optional[str] = None 
#     vote_time: datetime.datetime = field(default_factory=datetime.datetime.now)

#     @property
#     def user_id(self):
#         return self.user.id

# @dataclass
# class MockAction:
#     initiator: MockUser

# class MockProposal:
#     PROPOSED = "proposed"
#     PASSED = "passed"
#     FAILED = "failed"

#     def __init__(self, action: MockAction, created_at: datetime.datetime = None):
#         self.action = action
#         self.status = self.PROPOSED
#         self.data = MockDataStore()
#         self.votes: List[MockVote] = []
#         self.proposal_time = created_at or datetime.datetime.now()

#     def get_yes_votes(self, users=None):
#         votes = [v for v in self.votes if v.boolean_value is True]
#         if users:
#             votes = [v for v in votes if v.user in users]
#         return MockQuerySet(votes)

#     def get_no_votes(self, users=None):
#         votes = [v for v in self.votes if v.boolean_value is False]
#         if users:
#             votes = [v for v in votes if v.user in users]
#         return MockQuerySet(votes)
    
#     def get_all_boolean_votes(self, users=None):
#         votes = [v for v in self.votes if v.boolean_value is not None]
#         if users:
#             votes = [v for v in votes if v.user in users]
#         return MockQuerySet(votes)

#     def get_choice_votes(self, value=None):
#         if value:
#             votes = [v for v in self.votes if v.value == value]
#         else:
#             votes = [v for v in self.votes if v.value is not None]
#         return MockQuerySet(votes)

#     def get_time_elapsed(self):
#         return datetime.datetime.now() - self.proposal_time

#     def _pass_evaluation(self):
#         self.status = self.PASSED

#     def _fail_evaluation(self):
#         self.status = self.FAILED

# sys.modules["policyengine.models"].Proposal = MockProposal


# # ==========================================
# # 2. The Sandbox Executor
# # ==========================================

# def run_policy_check(code_str: str, proposal: MockProposal, users: List[MockUser]):
    
#     # 1. Prepare Global Scope
#     # [FIX] Added PASSED, FAILED, PROPOSED to global context
#     context = {
#         'proposal': proposal,
#         'action': proposal.action,
#         'users': users,
#         'datetime': datetime,
#         'Proposal': MockProposal,
#         'PASSED': "passed",
#         'FAILED': "failed",
#         'PROPOSED': "proposed"
#     }

#     try:
#         exec(code_str, context)
#     except Exception as e:
#         return f"CRASH (Syntax/Import): {e}"

#     if 'check' not in context:
#         return "ERROR: No 'check' function defined in code."
    
#     check_func = context['check']

#     sig = inspect.signature(check_func)
#     args = {}
    
#     for param in sig.parameters:
#         if param in context:
#             args[param] = context[param]
#         elif param == 'variables':
#             class MockVariables:
#                 pass
#             mock_vars = MockVariables()
#             mock_vars.proposal = proposal
#             if "winning_option" in code_str:
#                 mock_vars.winning_option = "Option A"
#             args[param] = mock_vars
            
#     try:
#         result = check_func(**args)
#         return result
#     except Exception as e:
#         return f"CRASH (Runtime): {e}"


# # ==========================================
# # 3. Dynamic Parser & Mock Data Injection
# # ==========================================

# def parse_output_file(file_path):
#     try:
#         with open(file_path, 'r') as f:
#             content = f.read()
#     except FileNotFoundError:
#         print(f"Error: Could not find file '{file_path}'")
#         return []

#     pattern = r"\[Test Case \d+/\d+\]:\s*(.*?)\n.*?[-]{30,}\n(.*?)\n\s*[-]{30,}"
#     matches = re.findall(pattern, content, re.DOTALL)
    
#     clean_matches = []
#     for name, code in matches:
#         clean_matches.append((name.strip(), code.strip()))
        
#     return clean_matches

# def get_mock_data_for_case(test_name, all_users):
#     alice = next(u for u in all_users if u.username == "alice")
#     action = MockAction(initiator=alice)
#     proposal = MockProposal(action)
    
#     if "Board" in test_name:
#         bob = next(u for u in all_users if u.username == "bob")
#         proposal.votes.append(MockVote(user=alice, boolean_value=True))
#         proposal.votes.append(MockVote(user=bob, boolean_value=False))
#         print(f"   [Context]: Board Member Alice=YES, Regular Bob=NO")

#     elif "Token" in test_name:
#         proposal.data.data["token_balances"] = {"alice": 100, "bob": 10}
#         bob = next(u for u in all_users if u.username == "bob")
#         proposal.votes.append(MockVote(user=alice, boolean_value=True))
#         proposal.votes.append(MockVote(user=bob, boolean_value=False))
#         print(f"   [Context]: Alice (100 tokens)=YES, Bob (10 tokens)=NO")

#     elif "Jury" in test_name:
#         jury_ids = [u.id for u in all_users]
#         proposal.data.data["jury_user_ids"] = jury_ids
#         proposal.votes.append(MockVote(user=all_users[0], boolean_value=True))
#         proposal.votes.append(MockVote(user=all_users[1], boolean_value=True))
#         proposal.votes.append(MockVote(user=all_users[2], boolean_value=False))
#         print(f"   [Context]: 3 Jurors. 2 YES, 1 NO.")

#     elif "Dictator" in test_name or "King" in test_name:
#         king = MockUser(username="king_arthur")
#         current_users = all_users + [king]
#         proposal.votes.append(MockVote(user=king, boolean_value=True))
#         print(f"   [Context]: King Arthur votes YES")
#         return proposal, current_users

#     elif "Ranked" in test_name:
#         proposal.votes.append(MockVote(user=all_users[0], value="Option A"))
#         proposal.votes.append(MockVote(user=all_users[1], value="Option A"))
#         proposal.votes.append(MockVote(user=all_users[2], value="Option B"))
#         print(f"   [Context]: 2 Votes for Option A, 1 for Option B")

#     else:
#         proposal.votes.append(MockVote(user=all_users[0], boolean_value=True))
#         proposal.votes.append(MockVote(user=all_users[1], boolean_value=True))
#         proposal.votes.append(MockVote(user=all_users[2], boolean_value=False))
#         print(f"   [Context]: Generic Majority Check (2 YES, 1 NO)")

#     return proposal, all_users


# # ==========================================
# # 4. Main Execution
# # ==========================================

# if __name__ == "__main__":
#     user_alice = MockUser(username="alice", id=1, roles=["Board Member"])
#     user_bob = MockUser(username="bob", id=2, roles=["Member"])
#     user_charlie = MockUser(username="charlie", id=3, roles=["Member"])
#     base_users = [user_alice, user_bob, user_charlie]

#     output_file = "output.txt"
#     extracted_cases = parse_output_file(output_file) 
    
#     print(f"Found {len(extracted_cases)} Test Cases in {output_file}\n")

#     for test_name, code_snippet in extracted_cases:
#         print(f"Running: {test_name}...")
#         proposal, users = get_mock_data_for_case(test_name, base_users)
#         result = run_policy_check(code_snippet, proposal, users)
#         print(f"   >> RESULT: {result}")
#         print("-" * 60)