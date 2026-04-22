from pydantic import BaseModel

class ToolInput(BaseModel):
    pass

class ToolOutput(BaseModel):
    result: str
