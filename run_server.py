import os
# Disable SQLAlchemy C extensions — they hang during DLL loading on this system
# (likely due to antivirus scanning .pyd files). Pure-Python fallback is used instead.
os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8003, reload=False)
