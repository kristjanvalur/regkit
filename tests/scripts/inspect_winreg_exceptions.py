import winreg

print("winreg module:", winreg)

# Create a key and close it, then try QueryValueEx on the closed handle
h = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, r"Software\FakeTestInspect", 0, winreg.KEY_ALL_ACCESS)
print("created handle type:", type(h))
h.Close()
try:
    winreg.QueryValueEx(h, "anything")
except Exception as e:
    print("closed-handle exception type:", type(e), repr(e))

# Try using an invalid predefined key
invalid_predef = 0xDEADBEEF
try:
    winreg.CreateKeyEx(invalid_predef, "sub", 0, winreg.KEY_ALL_ACCESS)
except Exception as e:
    print("invalid-predef exception type:", type(e), repr(e))
