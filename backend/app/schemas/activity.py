from pydantic import BaseModel, ConfigDict


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    campus: str
    location: str
    time: str
    tags: list[str]
    capacity: int
    public: bool
