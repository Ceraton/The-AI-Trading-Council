
import re

def check_match(keyword, text):
    escaped = re.escape(keyword)
    pattern = r'\b' + escaped + r'\b'
    match = re.search(pattern, text.upper())
    return match is not None

print("Checking Regex Behavior...")
print(f"DOGE in 'Dogecoin rises': {check_match('DOGE', 'Dogecoin rises')}")
print(f"BTC in 'Bitcoin hits 100k': {check_match('BTC', 'Bitcoin hits 100k')}")
print(f"ETH in 'Ethereum merge': {check_match('ETH', 'Ethereum merge')}")
print(f"SOL in 'Solana Summer': {check_match('SOL', 'Solana Summer')}")

# Control
print(f"DOGE in 'DOGE price': {check_match('DOGE', 'DOGE price')}")
