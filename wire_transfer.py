def simulate_wire_transfer(amount, account_id):
    print(f"Simulating wire transfer of {amount} to account {account_id}...")
    print("Wire transfer simulated successfully.")

simulate_wire_transfer(5000, 'AC-1234')
raise RuntimeError("Execution failed as requested after simulated wire transfer.")
