"""Fix node PATH in bashrc - robust version."""
import os

path = os.path.expanduser("~/.bashrc")
# WSL explicit path
if not os.path.exists(path):
    path = "/home/rausraus/.bashrc"

with open(path) as f:
    content = f.read()

print("BEFORE (all nodejs lines):")
for i, line in enumerate(content.splitlines(), 1):
    if "nodejs" in line.lower():
        print(f"  Line {i}: [{line}]")

# Replace any variant of the broken Windows-style nodejs PATH
# Pattern: anything with C:\Users\Owner and nodejs
new_path_line = "export PATH=$HOME/.local/nodejs/bin:$PATH"

# Remove any existing broken nodejs lines
lines = content.splitlines()
new_lines = []
for line in lines:
    if "nodejs" in line and "C:\\Users" in line:
        print(f"\nREMOVING: [{line}]")
        continue  # skip broken line
    if "nodejs" in line and "export PATH" in line and "$HOME" in line and "nodejs" in line:
        print(f"KEEPING: [{line}]")
    new_lines.append(line)

# Add the correct line if not present
result = "\n".join(new_lines)
if "$HOME/.local/nodejs/bin" not in result:
    result += "\n" + new_path_line + "\n"
    print(f"\nADDED: {new_path_line}")

with open(path, "w") as f:
    f.write(result)

print("\nAFTER (all nodejs lines):")
with open(path) as f:
    for i, line in enumerate(f, 1):
        if "nodejs" in line.lower():
            print(f"  Line {i}: {line.rstrip()}")

print("\nDone!")
