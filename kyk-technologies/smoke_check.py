import os
os.chdir(r'C:/Users/prashanth/Downloads/kyk-technologies/kyk-technologies')
import app
c = app.app.test_client()
for p in ['/', '/api/stats', '/api/jobs', '/api/insights']:
    r = c.get(p)
    print(p, r.status_code)
