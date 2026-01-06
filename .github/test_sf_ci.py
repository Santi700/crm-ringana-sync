import os
from simple_salesforce import Salesforce

u = (os.getenv("SF_USERNAME") or "").strip()
p = (os.getenv("SF_PASSWORD") or "").strip()
t = (os.getenv("SF_TOKEN") or "").strip()
d = (os.getenv("SF_DOMAIN") or "login").strip()

print("CI DEBUG USERNAME LEN:", len(u))
print("CI DEBUG PASSWORD LEN:", len(p))
print("CI DEBUG TOKEN LEN:", len(t))
print("CI DEBUG DOMAIN:", d)

sf = Salesforce(username=u, password=p, security_token=t, domain=d)
print("✅ CI LOGIN OK")
print(sf.query("SELECT Id, Name FROM Account LIMIT 1"))
