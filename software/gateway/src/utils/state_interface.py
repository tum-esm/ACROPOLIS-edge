import json
import pydantic
from utils.paths import STATE_PATH
from typing import Optional


class State(pydantic.BaseModel):
    """Persisting values over program executions."""
    offline_timestamp: Optional[int]


class StateInterface:

    @staticmethod
    def read() -> State:
        try:
            with open(STATE_PATH, "r") as f:
                return State(**json.load(f))
        except FileNotFoundError:
            print("state.json is missing, creating a new one")
        except Exception as e:
            print(f"state.json is invalid, creating a new one: {e}")

        new_empty_state = State(offline_since=None)
        StateInterface.write(new_state=new_empty_state)
        return new_empty_state

    @staticmethod
    def write(new_state: State) -> None:
        with open(STATE_PATH, "w") as f:
            json.dump(new_state.dict(), f)
