from roles_loader import load_role, pick_seed_question

# Test 1: software backend, medium
rd = load_role("engineer")
q = pick_seed_question(rd, branch="software", difficulty="medium")
print("Software / medium:", q)

# Test 2: electrical, hard
q2 = pick_seed_question(rd, branch="electrical", difficulty="hard")
print("Electrical / hard:", q2)

# Test 3: sales, medium
sd = load_role("sales")
q3 = pick_seed_question(sd, branch=None, difficulty="medium")
print("Sales / medium:", q3)

# Test 4: retail, easy
rdt = load_role("retail")
q4 = pick_seed_question(rdt, branch=None, difficulty="easy")
print("Retail / easy:", q4)
