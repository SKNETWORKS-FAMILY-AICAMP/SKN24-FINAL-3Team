from typing import Annotated

from pydantic import Field


FileSn = Annotated[int, Field(gt=0)]
