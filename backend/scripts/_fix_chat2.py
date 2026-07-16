import os
path = os.path.join(os.path.dirname(__file__), "..", "app", "routers", "chat.py")
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

old = chr(27599)+chr(27425)+chr(25805)+chr(20316)+chr(21518)+chr(27719)+chr(25253)+"verified"+chr(39564)+chr(35777)+chr(29366)+chr(24577)+chr(12290)+"\n\n"+chr(12304)+chr(27861)+chr(35268)+chr(24341)+chr(29992)+chr(35268)+chr(21017)
new = chr(27599)+chr(27425)+chr(25805)+chr(20316)+chr(21518)+chr(27719)+chr(25253)+"verified"+chr(39564)+chr(35777)+chr(29366)+chr(24577)+chr(12290)+chr(34)+"\n\n"+chr(12304)+chr(27861)+chr(35268)+chr(24341)+chr(29992)+chr(35268)+chr(21017)
content = content.replace(old, new)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed")