"""启动 uvicorn 服务"""
import os
os.environ["CHROMA_IS_PERSISTENT"] = "TRUE"
os.environ["CHROMA_PERSIST_DIRECTORY"] = os.path.join(os.path.dirname(__file__), "chroma_db")

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8094, reload=False)
