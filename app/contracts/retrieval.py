from pydantic import BaseModel, Field

class LoadedDocument(BaseModel):
    """Model representing a document loaded from the filesystem."""
    content: str = Field(description="The textual content of the document")
    source: str = Field(description="The source path of the document")
    type: str = Field(description="The file type/extension of the document")
