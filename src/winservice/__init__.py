"""winservice — giữ một tiến trình chạy 24/24 trên Windows."""

from .backoff import Backoff
from .supervisor import Supervisor
from .task import task_xml

__all__ = ["Backoff", "Supervisor", "task_xml"]
__version__ = "0.2.0"
